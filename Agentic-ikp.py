#!/usr/bin/env python3

"""agent-apply.py

 

Apply templates from agent-templates to multiple repos defined in a CSV.

 

Templating

---------

This script intentionally uses ONLY Python stdlib templating (no Jinja2) to

avoid conflicts with Helm's "{{ ... }}" syntax.

 

Template placeholder syntax is:

 

    @@TOKEN_NAME@@

 

Where TOKEN_NAME matches the CSV-derived token keys (e.g. APP_NAME).

 

Notes:

- Helm charts and Kubernetes manifests may contain "{{ ... }}" blocks; those are

    left untouched.

- Unknown placeholders are left as-is (safe substitution) so templates can

    deliberately keep Helm expressions.

"""

import argparse

import csv

import os

import shutil

import subprocess

import tempfile

from datetime import datetime

from string import Template

import re

import sys

import json

import urllib.request

import urllib.error

 

 

def _yaml_syntax_check(path):

    """Best-effort YAML syntax check.

 

    Uses PyYAML if available; otherwise falls back to a lightweight heuristic.

    """

    try:

        # Optional dependency; we don't require it.

        import yaml  # type: ignore

 

        with open(path, 'r', encoding='utf-8') as fh:

            yaml.safe_load(fh)

        return True, 'ok'

    except ModuleNotFoundError:

        # Heuristic: ensure file is readable and no unresolved placeholders.

        with open(path, 'r', encoding='utf-8') as fh:

            data = fh.read()

        if '@@' in data:

            return False, 'unresolved template placeholders (@@...@@)'

        return True, 'ok (PyYAML not installed)'

    except Exception as e:

        return False, str(e)

 

 

def _text_guardrails(path, *, forbidden_substrings=None):

    forbidden_substrings = forbidden_substrings or []

    with open(path, 'r', encoding='utf-8') as fh:

        data = fh.read()

    for s in forbidden_substrings:

        if s in data:

            return False, f'found forbidden substring: {s}'

    return True, 'ok'

 

 

class ATTemplate(Template):

    """Template using @@VARNAME@@ placeholders.

 

    We pick a delimiter that avoids collisions with Helm's {{ }} and also avoids

    accidental replacement of email addresses or common YAML content.

    """

 

    # Using delimiter '@@' would not work with string.Template (single char).

    # So we keep delimiter '@' but require the pattern @@NAME@@ via the regex.

    delimiter = '@'

    idpattern = r'[A-Z][_A-Z0-9]*'

 

 

def _normalize_tokens(tokens):

    """Expand token map so @@NAME@@ patterns can be matched reliably."""

    expanded = {}

    for k, v in tokens.items():

        expanded[k] = v

        expanded[f"@{k}"] = v

        expanded[f"{k}@"] = v

        expanded[f"@{k}@"] = v

    return expanded

 

 

def run(cmd, cwd=None, capture=False):

    print(f"RUN: {' '.join(cmd)} (cwd={cwd})")

    if capture:

        return subprocess.run(cmd, cwd=cwd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    return subprocess.run(cmd, cwd=cwd, check=False)

 

 

def render_template(template_dir, template_name, tokens):

    path = os.path.join(template_dir, template_name)

    with open(path, 'r', encoding='utf-8') as fh:

        content = fh.read()

    # Normalize any legacy @@NAME@@ placeholders to @NAME

    content = re.sub(r'@@([A-Z][_A-Z0-9]*)@@', r'@\1', content)

    tmpl = ATTemplate(content)

    rendered = tmpl.safe_substitute(tokens)

 

    # Basic guardrail: if a template still contains @@SOMETHING@@, that means a

    # token is missing (or typo). Keep it non-fatal, but make it visible.

    if '@@' in rendered:

        # Don't spam the whole file; just warn.

        print(f"WARN: Unresolved placeholders remain in template {template_name}")

    return rendered

 

 

def _parse_repo_owner_name(repo_url: str):

    """Extract (owner, repo) from a git remote URL.

 

    Supports typical HTTPS remotes such as:

      https://host/OWNER/REPO

      https://host/OWNER/REPO.git

    """

    repo_url = (repo_url or '').strip()

    # Strip trailing .git

    if repo_url.lower().endswith('.git'):

        repo_url = repo_url[:-4]

    # Trim possible trailing slash

    repo_url = repo_url.rstrip('/')

 

    parts = repo_url.split('/')

    if len(parts) < 2:

        raise ValueError(f"Cannot parse owner/repo from repoUrl: {repo_url}")

    owner = parts[-2]

    name = parts[-1]

    if not owner or not name:

        raise ValueError(f"Cannot parse owner/repo from repoUrl: {repo_url}")

    return owner, name

 

 

def _github_api_request(*, base_url: str, token: str, method: str, path: str, payload=None):

    """Make a GitHub Enterprise REST API request using a PAT."""

    if not base_url.endswith('/'):

        base_url = base_url + '/'

    url = base_url + path.lstrip('/')

 

    headers = {

        'Accept': 'application/vnd.github+json',

        # GHE accepts token auth via Authorization header

        'Authorization': f'token {token}',

        'User-Agent': 'agent-apply.py',

    }

    data = None

    if payload is not None:

        data = json.dumps(payload).encode('utf-8')

        headers['Content-Type'] = 'application/json'

 

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:

        with urllib.request.urlopen(req) as resp:

            body = resp.read().decode('utf-8')

            return resp.status, body

    except urllib.error.HTTPError as e:

        body = e.read().decode('utf-8') if e.fp else ''

        return e.code, body

 

 

def _create_pull_request(*, base_url: str, token: str, owner: str, repo: str, title: str, body: str, head: str, base: str):

    """Create a PR via GitHub REST API.

 

    API: POST /repos/{owner}/{repo}/pulls

    """

    payload = {

        'title': title,

        'body': body,

        'head': head,

        'base': base,

    }

    status, resp_body = _github_api_request(

        base_url=base_url,

        token=token,

        method='POST',

        path=f'/repos/{owner}/{repo}/pulls',

        payload=payload,

    )

    return status, resp_body

 

 

def main():

    p = argparse.ArgumentParser()

    p.add_argument('--csv', default='agent-templates/apps.csv')

    p.add_argument('--dry-run', action='store_true')

    p.add_argument('--tmpdir')

    p.add_argument('--git-api-base-url', default=os.environ.get('GIT_API_BASE_URL', 'https://alm-github.systems.uk.hsbc/api/v3/'))

    p.add_argument('--git-token', default=os.environ.get('GIT_TOKEN', os.environ.get('GITHUB_TOKEN', '')))

    args = p.parse_args()

 

    tmpdir = args.tmpdir or tempfile.mkdtemp(prefix='agent-apply-')

    template_dir = os.path.dirname(os.path.abspath(__file__))

 

    with open(args.csv) as fh:

        reader = csv.DictReader(fh)

        for row in reader:

            repo = row['repoUrl']

            branch = row['branch']

            app = row['appName']

            image_repo = row['imageRepo']

            lang = row.get('lang','jvm')

            skip_local = row.get('skipLocalBuild','false').lower()=='true'

 

            # Mandatory CSV fields check: ensure owners provided critical Dockerfile and image info

            # plus the configmap/secret references used by deployment template.

            required_csv = [

                'imageRepo',

                'appName',

                'base_image',

                'jar_file',

                'cm_env_config_name',

                'mongo_db_creds_secret_name',

                'cm_db_config_name',

                'ingress_hosts',

                'service_port',

                'service_target_port',

            ]

            missing_csv = [c for c in required_csv if not row.get(c)]

            if missing_csv:

                print(f"Missing required CSV columns {missing_csv} for repo {repo}. Skipping this entry.")

                continue

 

            workdir = os.path.join(tmpdir, app)

            print('Processing', app, repo)

 

            run(['git','clone',repo,workdir])

            run(['git','checkout',branch], cwd=workdir)

            new_branch = f'auto/devx-templates/{app}'

 

            # If branch already exists on remote, reuse it (checkout + pull).

            # Otherwise create it from the base branch.

            run(['git', 'fetch', '--prune', 'origin'], cwd=workdir)

            remote_head = run(['git', 'ls-remote', '--heads', 'origin', new_branch], cwd=workdir, capture=True)

            if remote_head.stdout.strip():

                print(f"Remote branch exists: {new_branch}. Checking out and pulling latest.")

                run(['git', 'checkout', new_branch], cwd=workdir)

                run(['git', 'pull', '--ff-only', 'origin', new_branch], cwd=workdir)

            else:

                run(['git', 'checkout', '-b', new_branch], cwd=workdir)

 

            tokens = {

                'APP_NAME': app,

                'IMAGE_REPO': image_repo,

                'TAG': datetime.utcnow().strftime('%Y%m%d%H%M%S'),

                # values.yaml.tmpl tokens (defaults chosen to mirror values-mct.yaml)

                'ENVIRONMENT': row.get('environment', 'mct'),

                'IMAGE_PULL_SECRET': row.get('imagePullSecret', 'docker-secret-agent'),

                'REPLICA_COUNT': row.get('replica_count', '1'),

                'IMAGE_PULL_POLICY': row.get('image_pull_policy', 'Always'),

                'LOGGING_AGENT_REPO': row.get('logging_agent_repo', f"{image_repo.rsplit('/', 1)[0]}/gcdu-splunk" if '/' in image_repo else image_repo),

                'LOGGING_AGENT_TAG': row.get('logging_agent_tag', '1.0.0'),

                'MONITORING_AGENT_REPO': row.get('monitoring_agent_repo', f"{image_repo.rsplit('/', 1)[0]}/datac-appd-agent-v1.8-24.7.1.36300" if '/' in image_repo else image_repo),

                'MONITORING_AGENT_TAG': row.get('monitoring_agent_tag', '1.0'),

                'APP_REQUEST_MEMORY': row.get('app_request_memory', '500Mi'),

                'APP_REQUEST_CPU': row.get('app_request_cpu', '150m'),

                'APP_LIMIT_MEMORY': row.get('app_limit_memory', '500Mi'),

                'APP_LIMIT_CPU': row.get('app_limit_cpu', '350m'),

                'LOG_REQUEST_CPU': row.get('log_request_cpu', '5m'),

                'LOG_REQUEST_MEMORY': row.get('log_request_memory', '128Mi'),

                'LOG_LIMIT_CPU': row.get('log_limit_cpu', '100m'),

                'LOG_LIMIT_MEMORY': row.get('log_limit_memory', '256Mi'),

                'MON_LIMIT_CPU': row.get('mon_limit_cpu', '80m'),

                'MON_LIMIT_MEMORY': row.get('mon_limit_memory', '850Mi'),

                'MON_REQUEST_CPU': row.get('mon_request_cpu', '80m'),

                'MON_REQUEST_MEMORY': row.get('mon_request_memory', '850Mi'),

                'SERVICE_TYPE': row.get('service_type', 'ClusterIP'),

                'SERVICE_PORT': row.get('service_port', '8080'),

                'SERVICE_TARGET_PORT': row.get('service_target_port', '8080'),

                'INGRESS_ENABLED': row.get('ingress_enabled', 'true'),

                'GIT_BRANCH': row.get('git_branch', ''),

                'SECONDARY_CLUSTER_ENABLED': row.get('secondary_cluster_enabled', 'false'),

                'PRIMARY_CLUSTER_ENABLED': row.get('primary_cluster_enabled', 'true'),

                'PRIMARY_CLUSTER_ENVIRONMENT': row.get('primary_cluster_environment', 'dev'),

                'PRIMARY_CLUSTER_MIN': row.get('primary_cluster_min', '1'),

                'PRIMARY_CLUSTER_MAX': row.get('primary_cluster_max', '1'),

                'PRIMARY_CLUSTER_CPU': row.get('primary_cluster_cpu', '55'),

                'PRIMARY_CLUSTER_MEM': row.get('primary_cluster_mem', '85'),

                'G3_ENV_MAP': row.get('g3_env_map','- { env: RWI, rcwi: rcwi-rwi }\n- { env: PWI, rcwi: rcwi-pwi }\n- { env: RCWI, rcwi: rcwi-prod }'),

 

                # ci-config specific tokens (optional, populated from CSV if present)

                'EIM': row.get('eim',''),

                'APPLICATION_VERSION': row.get('application_version','1.0.0'),

                'LOG_TRACE_ENABLED': row.get('log_trace_enabled','false'),

                'CONTAINER_IMAGE_TAG_DEFAULT': row.get('container_image_tag_default',''),

                'NON_PROD_ENV_DEFAULT': row.get('non_prod_env_default','UAT'),

                'SNAPSHOT_DEFAULT': row.get('snapshot_default','-SNAPSHOT'),

                'CR_NUMBER_DEFAULT': row.get('cr_number_default',''),

                'JDK_PATH': row.get('jdk_path','/usr/lib/jvm/default'),

                'MAVEN_PATH': row.get('maven_path','/usr/lib/maven'),

                'JIRA_CREDENTIAL_ID': row.get('jira_credential_id',''),

                'JIRA_HOST': row.get('jira_host',''),

                'BUILD_ENABLED': row.get('build_enabled','false'),

                'NEXUS_ID': row.get('nexus_id','nexus3uk'),

                'NEXUS_JENKINS_CRED': row.get('nexus_jenkins_cred','GB-SVC-CDMS-SHP'),

                'POM_PATH': row.get('pom_path','./pom.xml'),

                'MAVEN_GOAL': row.get('maven_goal','clean install'),

                'CONTAINER_BUILD_TYPE': row.get('container_build_type','kaniko'),

                'REGISTRY_NEXUS': row.get('registry_nexus', image_repo.split('/')[0] if '/' in image_repo else image_repo),

                'DOCKERFILE_LOCATION': row.get('dockerfile_location','.'),

                'APPLICATION_IMAGE_NAME': row.get('application_image_name', app),

                'TAG_EXPR': row.get('tag_expr','${params.container_image_tag}'),

                'DOCKER_JENKINS_CRED': row.get('docker_jenkins_cred','CDMS-SA-Docker-Config'),

                'IADP_ENABLED': row.get('iadp_enabled','false'),

                'IADP_CONTRACTS_PATH': row.get('iadp_contracts_path','api/contracts'),

                'PUBLISH_TO_ANY_ENABLED': row.get('publish_to_any_enabled','false'),

                'APIX_ENABLED': row.get('apix_enabled','false'),

                'G3_ENABLED': row.get('g3_enabled','true'),

                'G3_PROJECT_AREA': row.get('g3_project_area','Customer_Data_Mastering_Service'),

                'G3_APPLICATION_NAME': row.get('g3_application_name','CDMS-IKP'),

                'RWI_RELEASE_CONFIG_ID': row.get('rwi_release_config_id','8087086'),

                'NAMESPACE': row.get('namespace','default')

            }

 

            # Optional AppDynamics inputs for entrypoint.sh

            # We use two templates:

            # - entrypoint.sh.tmpl (no AppD flags)

            # - entrypoint-appd.sh.tmpl (includes AppD flags)

            appd_enabled_raw = (row.get('appd_enabled', 'false') or '').strip().lower()

            appd_enabled = appd_enabled_raw in ('true', 'yes', 'y', '1')

 

            # Ingress hosts: CSV provides comma-separated hosts. We generate two YAML blocks:

            # - INGRESS_HOSTS: list items under ingress.hosts

            # - INGRESS_TLS: list items under ingress.tls

            raw_hosts = row.get('ingress_hosts', '')

            hosts = [h.strip() for h in raw_hosts.split(',') if h.strip()]

            if not hosts:

                # keep valid YAML even if user doesn't provide hosts

                tokens['INGRESS_HOSTS'] = '    []'

                tokens['INGRESS_TLS'] = '    []'

            else:

                host_items = []

                for h in hosts:

                    host_items.extend([

                        f"    - host: {h}",

                        "      paths:",

                        "        - path: /",

                    ])

                tokens['INGRESS_HOSTS'] = "\n".join(host_items)

 

                tls_items = ["    - hosts:"]

                tls_items.extend([f"        - {h}" for h in hosts])

                tokens['INGRESS_TLS'] = "\n".join(tls_items)

 

            # Dockerfile-specific tokens: base_image and jar_file are mandatory (enforced above)

            tokens['BASE_IMAGE'] = row['base_image']

            tokens['JAR_FILE'] = row['jar_file']

            tokens['EXPOSE_PORT'] = row.get('expose_port','8092')

 

            # Deployment template configmap/secret references

            tokens['CM_ENV_CONFIG_NAME'] = row['cm_env_config_name']

            tokens['MONGO_DB_CREDS_SECRET_NAME'] = row['mongo_db_creds_secret_name']

            tokens['CM_DB_CONFIG_NAME'] = row['cm_db_config_name']

 

            # fail-fast checks for required tokens

            required_tokens = ['NEXUS_JENKINS_CRED','DOCKER_JENKINS_CRED']

            missing = [t for t in required_tokens if not tokens.get(t)]

            if missing:

                print(f"Missing required tokens: {missing}. Aborting for {app}.")

                continue

 

            # choose templates

            if lang in ('python','py'):

                ci_tmpl='ci-config.yaml.tmpl'

                docker_tmpl='Dockerfile.tmpl.python'

            else:

                ci_tmpl='ci-config.yaml.tmpl.jvm'

                docker_tmpl='Dockerfile.tmpl.jvm'

 

            # Indent multi-line G3_ENV_MAP for YAML block scalar in ci-config

            if ci_tmpl == 'ci-config.yaml.tmpl':

                tokens_ci = dict(tokens)

                g3_map = tokens_ci.get('G3_ENV_MAP', '')

                tokens_ci['G3_ENV_MAP'] = '\n'.join(('        ' + line) if line else '' for line in g3_map.splitlines())

                ci_out = render_template(template_dir, ci_tmpl, tokens_ci)

            else:

                ci_out = render_template(template_dir, ci_tmpl, tokens)

            with open(os.path.join(workdir,'ci-config.yaml'),'w') as fh_out:

                fh_out.write(ci_out)

 

            docker_out = render_template(template_dir, docker_tmpl, tokens)

            with open(os.path.join(workdir,'Dockerfile'),'w') as fh_out:

                fh_out.write(docker_out)

 

            # entrypoint.sh

            if appd_enabled:

                tokens['APPD_ACCOUNT_NAME'] = row.get('appd_account_name', '') or 'hsbc1'

                tokens['APPD_ACCOUNT_ACCESS_KEY'] = row.get('appd_account_access_key', '') or 'fb1f7622edf9'

                tokens['APPD_APPLICATION_NAME'] = row.get('appd_application_name', '') or 'cdms-cddm-uk-prod'

                tokens['APPD_NODE_NAME'] = row.get('appd_node_name', '') or 'cdms-syncback-service-Node-1.0.1'

                entrypoint_template = 'entrypoint-appd.sh.tmpl'

            else:

                # Keep the plain entrypoint output clean: no AppD placeholders needed.

                tokens.pop('APPD_ACCOUNT_NAME', None)

                tokens.pop('APPD_ACCOUNT_ACCESS_KEY', None)

                tokens.pop('APPD_APPLICATION_NAME', None)

                tokens.pop('APPD_NODE_NAME', None)

                entrypoint_template = 'entrypoint.sh.tmpl'

 

            entrypoint_out = render_template(template_dir, entrypoint_template, tokens)

            with open(os.path.join(workdir, 'entrypoint.sh'), 'w', encoding='utf-8', newline='\n') as fh_out:

                fh_out.write(entrypoint_out)

 

            # write helm chart: always create helm-<appName>/ with Chart.yaml, values.yaml,

            # and templates/ (service/ingress/hpa/serviceaccount)

            values_content = render_template(template_dir, 'values.yaml.tmpl', tokens)

            chart_dir = os.path.join(workdir, f"helm-{app}")

            os.makedirs(chart_dir, exist_ok=True)

            chart_yaml = render_template(template_dir, 'Chart.yaml.tmpl', tokens)

            with open(os.path.join(chart_dir,'Chart.yaml'),'w') as fh_chart:

                fh_chart.write(chart_yaml)

            with open(os.path.join(chart_dir,'values.yaml'),'w') as fh_out:

                fh_out.write(values_content)

 

            templates_dir = os.path.join(chart_dir, 'templates')

            os.makedirs(templates_dir, exist_ok=True)

 

            # Render additional helm templates.

            # These contain Helm double-curly blocks; only @@APP_NAME@@ (and any other @@TOKENS@@)

            # are substituted by our stdlib templater.

            for src_name, out_name in [

                ('deployment.yaml.tmpl', 'deployment.yaml'),

                ('service.yaml.tmpl', 'service.yaml'),

                ('ingress.yaml.tmpl', 'ingress.yaml'),

                ('hpa.yaml.tmpl', 'hpa.yaml'),

                ('serviceaccount.yaml.tmpl', 'serviceaccount.yaml'),

            ]:

                rendered = render_template(template_dir, src_name, tokens)

                with open(os.path.join(templates_dir, out_name), 'w', encoding='utf-8') as fh_tpl:

                    fh_tpl.write(rendered)

 

            print(f"Created chart directory and wrote Chart.yaml and values.yaml to: {chart_dir}")

 

            pr_body = render_template(template_dir, 'PR_TEMPLATE.md.tmpl', {'APP_NAME':app,'DOCKER_RESULT':'pending','HELM_RESULT':'pending','TEST_RESULT':'pending'})

            with open(os.path.join(workdir,'PR_BODY.md'),'w') as fh_out:

                fh_out.write(pr_body)

 

            if not args.dry_run:

                # Pre-PR checks: keep it lightweight.

                # No Maven build, no Docker build, no Helm lint required.

                checks = []

                checks.append(('ci-config.yaml (yaml)',) + _yaml_syntax_check(os.path.join(workdir, 'ci-config.yaml')))

                checks.append((f'helm-{app}/Chart.yaml (yaml)',) + _yaml_syntax_check(os.path.join(chart_dir, 'Chart.yaml')))

                checks.append((f'helm-{app}/values.yaml (yaml)',) + _yaml_syntax_check(os.path.join(chart_dir, 'values.yaml')))

                # These are Helm templates; do placeholder guardrails (not YAML parse).

                checks.append((f'helm-{app}/templates/deployment.yaml (placeholders)',) + _text_guardrails(os.path.join(templates_dir, 'deployment.yaml'), forbidden_substrings=['@@']))

                checks.append((f'helm-{app}/templates/service.yaml (placeholders)',) + _text_guardrails(os.path.join(templates_dir, 'service.yaml'), forbidden_substrings=['@@']))

                checks.append((f'helm-{app}/templates/ingress.yaml (placeholders)',) + _text_guardrails(os.path.join(templates_dir, 'ingress.yaml'), forbidden_substrings=['@@']))

                checks.append((f'helm-{app}/templates/hpa.yaml (placeholders)',) + _text_guardrails(os.path.join(templates_dir, 'hpa.yaml'), forbidden_substrings=['@@']))

                checks.append((f'helm-{app}/templates/serviceaccount.yaml (placeholders)',) + _text_guardrails(os.path.join(templates_dir, 'serviceaccount.yaml'), forbidden_substrings=['@@']))

                # Dockerfile: ensure it doesn't still have unresolved placeholders.

                checks.append(('Dockerfile (placeholders)',) + _text_guardrails(os.path.join(workdir, 'Dockerfile'), forbidden_substrings=['@@'] ))

                checks.append(('entrypoint.sh (placeholders)',) + _text_guardrails(os.path.join(workdir, 'entrypoint.sh'), forbidden_substrings=['@@'] ))

 

                failed = [(name, msg) for (name, ok, msg) in checks if not ok]

                for (name, ok, msg) in checks:

                    print(f"CHECK: {name}: {'PASS' if ok else 'FAIL'} ({msg})")

                if failed:

                    print('One or more syntax checks failed; skipping commit/push/PR for this repo:')

                    for name, msg in failed:

                        print(f" - {name}: {msg}")

                    continue

 

                run([

                    'git','add',

                    'ci-config.yaml',

                    'Dockerfile',

                    'entrypoint.sh',

                    os.path.join(f'helm-{app}','Chart.yaml'),

                    os.path.join(f'helm-{app}','values.yaml'),

                    os.path.join(f'helm-{app}','templates','deployment.yaml'),

                    os.path.join(f'helm-{app}','templates','service.yaml'),

                    os.path.join(f'helm-{app}','templates','ingress.yaml'),

                    os.path.join(f'helm-{app}','templates','hpa.yaml'),

                    os.path.join(f'helm-{app}','templates','serviceaccount.yaml'),

                    'PR_BODY.md'

                ], cwd=workdir)

                run(['git','commit','-m',f"add DevX/IKP templates for {app}"], cwd=workdir)

                run(['git','push','-u','origin',new_branch], cwd=workdir)

 

                # Create PR via Git REST API (GitHub Enterprise) using a token.

                if not args.git_token:

                    print('GIT token not provided (use --git-token or env GIT_TOKEN/GITHUB_TOKEN); please create PR manually')

                else:

                    try:

                        owner, repo_name = _parse_repo_owner_name(repo)

                        with open(os.path.join(workdir, 'PR_BODY.md'), 'r', encoding='utf-8') as fh:

                            pr_body_text = fh.read()

 

                        # For GitHub API, head may be either "branch" (same repo) or "owner:branch".

                        # Using "owner:branch" is explicit and works for same-repo PRs.

                        head_ref = f"{owner}:{new_branch}"

                        title = f"Feat: add DevX/IKP templates for {app}"

 

                        status, resp_body = _create_pull_request(

                            base_url=args.git_api_base_url,

                            token=args.git_token,

                            owner=owner,

                            repo=repo_name,

                            title=title,

                            body=pr_body_text,

                            head=head_ref,

                            base=branch,

                        )

                        if status in (200, 201):

                            # Parse response to get PR URL
                            try:
                                pr_data = json.loads(resp_body)
                                pr_url = pr_data.get('html_url', '')
                                pr_number = pr_data.get('number', '')
                                if pr_url:
                                    print(f'PR created successfully: {pr_url}')
                                    print(f'PR_URL={pr_url}')  # Machine-readable format for backend parsing
                                else:
                                    print('PR created successfully')
                            except:
                                print('PR created successfully')

                        else:

                            print(f"PR creation failed (HTTP {status}). Response: {resp_body}")

                    except Exception as e:

                        print(f"PR creation failed due to error: {e}. Please create PR manually.")

 

    if args.tmpdir is None:

        print('Leaving tempdir for inspection:', tmpdir)

 

 

if __name__ == '__main__':

    main()