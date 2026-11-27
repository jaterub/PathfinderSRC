"""GitHub transport for the shared canonical synchronizer (stdlib only).

Read-only Project pagination and identity checks are adapted from Fable Five.
Issue operations and native hierarchy use the same API as Profession.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from canonical_plan import index_issues

API = "https://api.github.com"


def request(method, url, token, payload=None, allow_404=False):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "canonical-kanban",
    })
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        if allow_404 and method == "GET" and exc.code == 404:
            return None
        raise RuntimeError(f"GitHub {method} returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("GitHub transport failed") from exc


SCOPE = """query($id:ID!,$cursor:String) {
  node(id:$id) { ... on ProjectV2 { id title closed template viewerCanUpdate
    repositories(first:100,after:$cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner }
    }
  } }
}"""
FIELDS = """query($id:ID!,$cursor:String) {
  node(id:$id) { ... on ProjectV2 { id title
    fields(first:100,after:$cursor) { pageInfo { hasNextPage endCursor }
      nodes { ... on ProjectV2SingleSelectField { id name options { id name } } }
    }
  } }
}"""
ITEMS = """query($id:ID!,$cursor:String) {
  node(id:$id) { ... on ProjectV2 { id title
    items(first:100,after:$cursor,archivedStates:[ARCHIVED,NOT_ARCHIVED]) {
      pageInfo { hasNextPage endCursor }
      nodes { id isArchived content { __typename
        ... on Issue { id number repository { nameWithOwner } }
      }
      fieldValues(first:100) { pageInfo { hasNextPage } nodes {
        ... on ProjectV2ItemFieldSingleSelectValue {
          name field { ... on ProjectV2SingleSelectField { id name } }
        }
      } }
      }
    }
  } }
}"""


class GitHub:
    def __init__(self, config, issue_token, project_token, *, writable=False, transport=request):
        if not issue_token or not project_token:
            raise ValueError("missing GitHub Issues or Projects token")
        self.config = config
        self.repo = config["repository"]
        self.project_id = config["project_id"]
        self.issue_token, self.project_token = issue_token, project_token
        self.writable, self.transport = writable, transport
        self.card_ids = {}
        self.field_id = None
        self.options = {}

    def rest(self, method, path, payload=None, allow_404=False):
        if method != "GET" and not self.writable:
            raise RuntimeError("read-only mode cannot mutate Issues")
        return self.transport(method, f"{API}/repos/{self.repo}/{path}", self.issue_token, payload, allow_404)

    def gql(self, query, variables):
        if not query.lstrip().startswith("query") and not self.writable:
            raise RuntimeError("read-only mode cannot mutate Projects")
        response = self.transport("POST", API + "/graphql", self.project_token,
                                  {"query": query, "variables": variables}, False)
        if not isinstance(response, dict) or response.get("errors") or not isinstance(response.get("data"), dict):
            raise RuntimeError("GitHub Projects GraphQL rejected request")
        return response["data"]

    def rest_pages(self, path):
        out = []
        sep = "&" if "?" in path else "?"
        for page in range(1, 31):
            batch = self.rest("GET", f"{path}{sep}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise ValueError("unexpected GitHub list response")
            out.extend(batch)
            if len(batch) < 100:
                return out
        raise ValueError("REST pagination ceiling reached")

    def project_pages(self, query, field):
        cursor, seen, rows = None, set(), []
        for _ in range(100):
            response = self.gql(query, {"id": self.project_id, "cursor": cursor})
            node = response.get("node")
            if (not node or node.get("id") != self.project_id
                    or node.get("title") != self.config["project_title"]):
                raise ValueError("Project identity/title mismatch")
            if field == "repositories":
                if node.get("closed") is not False or node.get("template") is not False:
                    raise ValueError("Project is closed, a template, or its state is unavailable")
                if self.writable and node.get("viewerCanUpdate") is not True:
                    raise ValueError("Projects token cannot update the configured board")
            conn = node.get(field)
            if not isinstance(conn, dict) or not isinstance(conn.get("nodes"), list):
                raise ValueError("missing Project connection")
            rows.extend(conn["nodes"])
            page = conn.get("pageInfo") or {}
            if type(page.get("hasNextPage")) is not bool:
                raise ValueError("missing Project pagination state")
            if not page["hasNextPage"]:
                return rows
            cursor = page.get("endCursor")
            if not cursor or cursor in seen:
                raise ValueError("invalid/repeated Project cursor")
            seen.add(cursor)
        raise ValueError("Project pagination ceiling reached")

    def verify_scope(self):
        linked = self.project_pages(SCOPE, "repositories")
        if self.repo.casefold() not in {(r.get("nameWithOwner") or "").casefold() for r in linked if r}:
            raise ValueError("Project is not linked to the configured repository")

    def board(self):
        self.verify_scope()
        fields = [f for f in self.project_pages(FIELDS, "fields")
                  if f and f.get("name") == "Status" and f.get("options")]
        if len(fields) != 1 or not fields[0].get("id"):
            raise ValueError("Project must have one Status field")
        field = fields[0]
        options = {}
        for item in field["options"]:
            label = item["name"].strip().casefold()
            if label in options or not item.get("id"):
                raise ValueError("ambiguous Project Status option")
            options[label] = item["id"]
        cards = []
        for item in self.project_pages(ITEMS, "items"):
            content = item.get("content")
            if not isinstance(content, dict) or not content.get("__typename"):
                raise ValueError("Project item content is unreadable; verify token access")
            values = item.get("fieldValues") or {}
            if not isinstance(values.get("nodes"), list) or (values.get("pageInfo") or {}).get("hasNextPage") is not False:
                raise ValueError("incomplete Project card field values")
            status = [v.get("name") for v in values["nodes"] if v and (v.get("field") or {}).get("id") == field["id"]]
            if len(status) > 1:
                raise ValueError("ambiguous card Status")
            cards.append({"id": item["id"], "archived": item.get("isArchived"),
                          "repository": (content.get("repository") or {}).get("nameWithOwner"),
                          "number": content.get("number"), "content_id": content.get("id"),
                          "status": status[0] if status else None})
        self.field_id, self.options = field["id"], options
        return {"field": field["id"], "options": options, "cards": sorted(cards, key=lambda c: c["id"])}

    def same_repo(self, item):
        expected = f"{API}/repos/{self.repo}".casefold()
        actual = (item.get("repository_url") or "").casefold()
        if actual != expected or not isinstance(item.get("number"), int):
            raise ValueError("native Issue belongs to another/unknown repository")
        return item["number"]

    def snapshot(self):
        board = self.board()
        issues = sorted((i for i in self.rest_pages("issues?state=all") if "pull_request" not in i),
                        key=lambda i: i["number"])
        # Keep only values relevant to reconciliation, not entire issue payloads.
        issues = [{k: i.get(k) for k in ("number", "id", "node_id", "title", "body", "state", "state_reason")}
                  for i in issues]
        indexed, _ = index_issues(issues, self.config)
        parents, children = {}, {}
        for item in indexed.values():
            number = item["number"]
            parent = self.rest("GET", f"issues/{number}/parent", allow_404=True)
            parents[number] = self.same_repo(parent) if parent else None
            children[number] = sorted(self.same_repo(c) for c in self.rest_pages(f"issues/{number}/sub_issues"))
        self.card_ids = {key: c["id"] for key, i in indexed.items() for c in board["cards"]
                         if not c["archived"] and c["number"] == i["number"]
                         and (c.get("repository") or "").casefold() == self.repo.casefold()}
        return {"issues": issues, "parents": parents, "children": children, "board": board}

    def execute(self, action, indexed):
        key, kind = action["id"], action["kind"]
        if kind == "create":
            value = self.rest("POST", "issues", {"title": action["title"],
                "body": f"Canonical source: [CONTEXTO.md](https://github.com/{self.repo}/blob/main/CONTEXTO.md)\n\n<!-- {self.config['marker']}: {key} -->"})
            if not isinstance(value.get("number"), int) or not value.get("id") or not value.get("node_id"):
                raise RuntimeError("Issue creation response missing identity")
            indexed[key] = value
            return
        issue = indexed[key]
        number = issue["number"]
        if kind in ("title", "state"):
            payload = {kind: action["value"]}
            if "reason" in action:
                payload["state_reason"] = action["reason"]
            result = self.rest("PATCH", f"issues/{number}", payload)
            if result.get("number") != number:
                raise RuntimeError("Issue update identity mismatch")
        elif kind in ("attach", "detach"):
            parent = indexed[action["parent"]]["number"]
            endpoint = "sub_issues" if kind == "attach" else "sub_issue"
            self.rest("POST" if kind == "attach" else "DELETE", f"issues/{parent}/{endpoint}",
                      {"sub_issue_id": issue["id"]})
        elif kind == "add_card":
            result = self.gql("""mutation($p:ID!,$c:ID!) {
              addProjectV2ItemById(input:{projectId:$p,contentId:$c}) { item { id } }
            }""", {"p": self.project_id, "c": issue["node_id"]})
            card = (result.get("addProjectV2ItemById") or {}).get("item") or {}
            if not card.get("id"):
                raise RuntimeError("Project card creation not confirmed")
            self.card_ids[key] = card["id"]
        elif kind in ("archive", "unarchive"):
            mutation = "archiveProjectV2Item" if kind == "archive" else "unarchiveProjectV2Item"
            result = self.gql("mutation($p:ID!,$i:ID!) {" + mutation
                + "(input:{projectId:$p,itemId:$i}) { item { id } }}",
                {"p": self.project_id, "i": action["card"]})
            if ((result.get(mutation) or {}).get("item") or {}).get("id") != action["card"]:
                raise RuntimeError("Project membership update not confirmed")
            if kind == "unarchive":
                self.card_ids[key] = action["card"]
            else:
                self.card_ids.pop(key, None)
        elif kind == "card_status":
            card = self.card_ids[key]
            result = self.gql("""mutation($p:ID!,$i:ID!,$f:ID!,$o:String!) {
              updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f,
                value:{singleSelectOptionId:$o}}) { projectV2Item { id } }
            }""", {"p": self.project_id, "i": card, "f": self.field_id,
                    "o": self.options[action["value"].casefold()]})
            if ((result.get("updateProjectV2ItemFieldValue") or {}).get("projectV2Item") or {}).get("id") != card:
                raise RuntimeError("Project Status mutation not confirmed")
        else:
            raise ValueError("unknown action: " + kind)
