"""Read-only, paginated Project V2 backup adapted from Fable Five.

Captures Project fields and every item field value with pagination. For unknown
field types, retain raw JSON and STOP release approval rather than pretend this
can restore values. No GitHub mutations in this module.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

PROJECT_QUERY = '''query($id: ID!, $cursor: String) {
 node(id:$id) { ... on ProjectV2 { id title
  fields(first:100,after:$cursor) { nodes { __typename
   ... on ProjectV2Field { id name dataType }
   ... on ProjectV2SingleSelectField { id name dataType options {id name} }
   ... on ProjectV2MultiSelectField { id name dataType multiSelectOptions {id name} }
   ... on ProjectV2IterationField { id name dataType configuration {iterations {id title startDate duration} completedIterations {id title startDate duration}} }
  } pageInfo {hasNextPage endCursor} }
 } }
}'''
ITEMS_QUERY = '''query($id: ID!, $cursor: String) {
 node(id:$id) { ... on ProjectV2 { id title items(first:100,after:$cursor,archivedStates:[ARCHIVED,NOT_ARCHIVED]) {
  nodes { id type isArchived content {
   __typename
   ... on Issue { id number url title body state repository { nameWithOwner } }
   ... on PullRequest { id number url title state repository { nameWithOwner } }
   ... on DraftIssue { id title body }
  } }
  pageInfo {hasNextPage endCursor} }
 } }
}'''
VALUES_QUERY = '''query($id: ID!, $cursor: String) {
 node(id:$id) { ... on ProjectV2Item { id fieldValues(first:100,after:$cursor) {
  nodes { __typename
   ... on ProjectV2ItemFieldSingleSelectValue { optionId name field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldTextValue { text field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldNumberValue { number field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldDateValue { date field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldIterationValue { iterationId title startDate duration field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldMultiSelectValue { options {id name} field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldLabelValue { labels(first:100) { nodes {id name} pageInfo {hasNextPage} } field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldMilestoneValue { milestone {id title} field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldRepositoryValue { repository {id nameWithOwner} field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldUserValue { users(first:100) { nodes {id login} pageInfo {hasNextPage} } field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldPullRequestValue { pullRequests(first:100) { nodes {id} pageInfo {hasNextPage} } field {... on ProjectV2FieldCommon {id name}} }
   ... on ProjectV2ItemFieldReviewerValue { reviewers(first:100) { nodes {__typename ... on Node {id}} pageInfo {hasNextPage} } field {... on ProjectV2FieldCommon {id name}} }
  }
  pageInfo {hasNextPage endCursor} }
 } }
}'''

KNOWN_TYPES = frozenset({
 'ProjectV2ItemFieldSingleSelectValue','ProjectV2ItemFieldTextValue',
 'ProjectV2ItemFieldNumberValue','ProjectV2ItemFieldDateValue',
 'ProjectV2ItemFieldIterationValue','ProjectV2ItemFieldMultiSelectValue','ProjectV2ItemFieldLabelValue',
 'ProjectV2ItemFieldMilestoneValue',
 'ProjectV2ItemFieldRepositoryValue',
})

class SnapshotStop(RuntimeError):
    pass


def _paged(fetch, query, project_or_item_id, path, *, page_cap=100):
    cursor = None
    seen = set()
    all_nodes = []
    for _ in range(page_cap):
        result = fetch(query, {'id': project_or_item_id, 'cursor': cursor})
        if not isinstance(result, dict) or result.get('errors') or not isinstance(result.get('data'), dict):
            raise SnapshotStop('GraphQL error or inaccessible data')
        node = result['data'].get('node')
        if not isinstance(node, dict) or node.get('id') != project_or_item_id:
            raise SnapshotStop('GraphQL node identity mismatch')
        connection = node.get(path)
        if not isinstance(connection, dict) or not isinstance(connection.get('nodes'), list):
            raise SnapshotStop('missing connection '+path)
        all_nodes.extend(connection['nodes'])
        page = connection.get('pageInfo')
        if not isinstance(page, dict) or not isinstance(page.get('hasNextPage'), bool):
            raise SnapshotStop('missing pagination state')
        if not page['hasNextPage']:
            return node, all_nodes
        nxt = page.get('endCursor')
        if not nxt or nxt in seen:
            raise SnapshotStop('missing or repeated cursor')
        seen.add(nxt)
        cursor = nxt
    raise SnapshotStop('pagination safety ceiling reached')


def capture(fetch, *, project_id, project_title, repository, historical_numbers=()):
    if not (project_id and project_title and repository):
        raise SnapshotStop('missing Project identity')
    if len(set(historical_numbers)) != len(historical_numbers):
        raise SnapshotStop('duplicate historical Issue numbers')
    project, fields = _paged(fetch, PROJECT_QUERY, project_id, 'fields')
    if project.get('title') != project_title:
        raise SnapshotStop('Project title mismatch')
    _, items = _paged(fetch, ITEMS_QUERY, project_id, 'items')
    if len({i.get('id') for i in items}) != len(items) or any(not i.get('id') for i in items):
        raise SnapshotStop('duplicate/unidentified Project card')
    # A card's GraphQL ID is its exact Project membership; no silent assumptions.
    card_records = []
    issue_memberships = set()
    unknown_types = set()
    for item in items:
        _, values = _paged(fetch, VALUES_QUERY, item['id'], 'fieldValues')
        field_ids = []
        for value in values:
            if not value:
                continue
            typename = value.get('__typename')
            if typename not in KNOWN_TYPES:
                unknown_types.add(str(typename))
            field = value.get('field') or {}
            if typename in KNOWN_TYPES and (not field.get('id') or field['id'] in field_ids):
                raise SnapshotStop('missing/duplicate field identity on card '+item['id'])
            if field.get('id'):
                field_ids.append(field['id'])
            for name in ('labels', 'users', 'pullRequests', 'reviewers'):
                conn = value.get(name)
                if conn and (conn.get('pageInfo') or {}).get('hasNextPage') is not False:
                    raise SnapshotStop('incomplete nested pagination: '+name)
        content = item.get('content')
        if not isinstance(content, dict) or not content.get('__typename'):
            raise SnapshotStop('unreadable card content; verify token access')
        if content.get('repository', {}).get('nameWithOwner') == repository and content.get('__typename') == 'Issue':
            number = content.get('number')
            # Archived memberships may coexist with a replacement active card
            # after a failed/rolled-back cutover. Only duplicate ACTIVE cards
            # are ambiguous; preserve all archived cards for audit.
            if not item.get('isArchived'):
                if number in issue_memberships:
                    raise SnapshotStop('duplicate active Issue card #'+str(number))
                issue_memberships.add(number)
        card_records.append({'id':item['id'],'type':item.get('type'), 'is_archived':item.get('isArchived'), 'content':content, 'values':values})
    # Snapshot includes all cards, including cards from other repositories and drafts.
    data = {
        'schema':'canonical-project-v2-backup-v2',
        'captured_at_utc':datetime.now(timezone.utc).isoformat(),
        'project_id':project_id,'project_title':project_title,
        'repository':repository, 'historical_issue_numbers':sorted(historical_numbers),
        'fields':fields,'cards':card_records,
        'unknown_value_types': sorted(unknown_types),
        'write_eligible': not unknown_types,
    }
    return data


def stable_hash(data):
    material = {k:v for k,v in data.items() if k != 'captured_at_utc'}
    return hashlib.sha256(json.dumps(material,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def compare_semantic(before, after):
    """Detect any card membership/field drift; card ID equality is intentional.

    A deleted and recreated card gets a new ID: this method must not claim that
    deletion + recreation is a bitwise rollback. Repair requires a separate plan.
    """
    fields = ('project_id','project_title','repository','fields','cards','historical_issue_numbers')
    for key in fields:
        if before.get(key) != after.get(key):
            raise SnapshotStop('Project state differs: '+key)
    if before.get('unknown_value_types') or after.get('unknown_value_types'):
        raise SnapshotStop('unsupported Project field values')
    return True


def write_backup(path, snapshot):
    """Create a private local backup; never replace a previous backup."""
    path = Path(path)
    envelope = {"sha256": stable_hash(snapshot), "snapshot": snapshot}
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(envelope, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    read_backup(path)
    return envelope["sha256"]


def read_backup(path):
    envelope = json.loads(Path(path).read_text(encoding="utf-8"))
    if envelope.get("sha256") != stable_hash(envelope["snapshot"]):
        raise SnapshotStop("backup checksum mismatch")
    return envelope["snapshot"]


def main(argv=None):
    from canonical_config import load_config
    from canonical_github import API, request

    parser = argparse.ArgumentParser(description="Read-only private Project backup")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    target = args.out.resolve()
    if target == root or root in target.parents:
        raise SnapshotStop("backup must be stored outside the repository")
    if target.exists():
        raise SnapshotStop("refusing to overwrite a backup")
    config = load_config(root, args.repo)
    token = os.environ.get("PROJECTS_TOKEN")
    if not token:
        raise SnapshotStop("missing read-enabled PROJECTS_TOKEN")

    def fetch(query, variables):
        if not query.lstrip().startswith("query"):
            raise SnapshotStop("backup cannot execute mutations")
        return request("POST", API + "/graphql", token, {"query": query, "variables": variables})

    snapshot = capture(fetch, project_id=config["project_id"], project_title=config["project_title"],
                       repository=config["repository"])
    checksum = write_backup(target, snapshot)
    if not snapshot["write_eligible"]:
        raise SnapshotStop("backup saved but unsupported field types prevent migration approval")
    if args.compare:
        compare_semantic(read_backup(args.compare), snapshot)
    print(f"PASS: {len(snapshot['cards'])} cards; SHA-256={checksum}")


if __name__ == "__main__":
    main()
