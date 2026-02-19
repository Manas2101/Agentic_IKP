#!/usr/bin/env python3

"""

agent-apply.py

Apply templates from agent-templates to multiple repos defined in a CSV.

- Uses Jinja2 for templating

- Calls git, docker, helm and mvn via subprocess

- Creates PRs via gh CLI if available

"""

import argparse

import csv

import os

import shutil

import subprocess

import tempfile

from datetime import datetime

import re

 

def run(cmd, cwd=None, capture=False):

    print(f"RUN: {' '.join(cmd)} (cwd={cwd})")

    if capture:

        return subprocess.run(cmd, cwd=cwd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    return subprocess.run(cmd, cwd=cwd, check=False)

 

_TOKEN_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")

 

def render_template(template_path, tokens):

    """Render a simple template using only Python built-ins.

 

    Supported syntax:

      - {{TOKEN_NAME}} replaced by tokens['TOKEN_NAME'] (converted to str)

 

    Notes:

      - This intentionally avoids full Jinja2 features (loops/conditionals/filters).

      - If a token is missing, we fail fast with a KeyError to avoid silently

        generating invalid configs.

    """

    with open(template_path, encoding='utf-8') as f:

        content = f.read()

 

    def repl(match: re.Match) -> str:

        key = match.group(1)

        if key not in tokens:

            raise KeyError(f"Missing template token: {key} (template: {template_path})")

        return str(tokens[key])

 

    return _TOKEN_RE.sub(repl, content)

 

def main():

    p = argparse.ArgumentParser()

    p.add_argument('--csv', default='agent-templates/apps.csv')

    p.add_argument('--dry-run', action='store_true')

    p.add_argument('--tmpdir')

    args = p.parse_args()

 

    tmpdir = args.tmpdir or tempfile.mkdtemp(prefix='agent-apply-')

    templates_dir = os.path.abspath('agent-templates')

 

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

            required_csv = ['imageRepo','appName','base_image','jar_file']

            missing_csv = [c for c in required_csv if not row.get(c)]

            if missing_csv:

                print(f"Missing required CSV columns {missing_csv} for repo {repo}. Skipping this entry.")

                continue

 

            workdir = os.path.join(tmpdir, app)

            print('Processing', app, repo)

 

            run(['git','clone',repo,workdir])

            run(['git','checkout',branch], cwd=workdir)

            new_branch = f'automation/hdpv2-templates/{app}'

            run(['git','checkout','-b',new_branch], cwd=workdir)

 

            tokens = {

                'APP_NAME': app,

                'IMAGE_REPO': image_repo,

                'TAG': datetime.utcnow().strftime('%Y%m%d%H%M%S'),

                'IMAGE_PULL_SECRET': row.get('imagePullSecret','nexus-registry'),

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

 

            # Dockerfile-specific tokens: base_image and jar_file are mandatory (enforced above)

            tokens['BASE_IMAGE'] = row['base_image']

            tokens['JAR_FILE'] = row['jar_file']

            tokens['EXPOSE_PORT'] = row.get('expose_port','8092')

 

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

 

            ci_out = render_template(os.path.join(templates_dir, ci_tmpl), tokens)

            with open(os.path.join(workdir,'ci-config.yaml'),'w') as fh_out:

                fh_out.write(ci_out)

 

            docker_out = render_template(os.path.join(templates_dir, docker_tmpl), tokens)

            with open(os.path.join(workdir,'Dockerfile'),'w') as fh_out:

                fh_out.write(docker_out)

 

            # write values.yaml: always create helm-<appName>/ with Chart.yaml and values.yaml to match repo structure

            values_content = render_template(os.path.join(templates_dir, 'values.yaml.tmpl'), tokens)

            chart_dir = os.path.join(workdir, f"helm-{app}")

            os.makedirs(chart_dir, exist_ok=True)

            chart_yaml = render_template(os.path.join(templates_dir, 'Chart.yaml.tmpl'), tokens)

            with open(os.path.join(chart_dir,'Chart.yaml'),'w') as fh_chart:

                fh_chart.write(chart_yaml)

            with open(os.path.join(chart_dir,'values.yaml'),'w') as fh_out:

                fh_out.write(values_content)

            print(f"Created chart directory and wrote Chart.yaml and values.yaml to: {chart_dir}")

 

            pr_body = render_template(

                os.path.join(templates_dir, 'PR_TEMPLATE.md.tmpl'),

                {'APP_NAME': app, 'DOCKER_RESULT': 'pending', 'HELM_RESULT': 'pending', 'TEST_RESULT': 'pending'},

            )

            with open(os.path.join(workdir,'PR_BODY.md'),'w') as fh_out:

                fh_out.write(pr_body)

 

            if not args.dry_run:

                # run mvn build for jvm

                if not skip_local and lang in ('jvm','java'):

                    if os.path.exists(os.path.join(workdir,'mvnw')):

                        run(['./mvnw','-B','-DskipTests','package'], cwd=workdir)

                    else:

                        run(['mvn','-B','-DskipTests','package'], cwd=workdir)

 

                # docker build

                if not skip_local:

                    run(['docker','build','-t',f"{image_repo}:{tokens['TAG']}",'.'], cwd=workdir)

 

                # helm lint

                run(['helm','lint', '.'], cwd=workdir)

 

                run(['git','add','ci-config.yaml','Dockerfile','values.yaml','PR_BODY.md'], cwd=workdir)

                run(['git','commit','-m',f"chore: add HDPV2/IKP templates for {app}"], cwd=workdir)

                run(['git','push','-u','origin',new_branch], cwd=workdir)

 

                # create PR via gh if available

                gh = shutil.which('gh')

                if gh:

                    run(['gh','pr','create','--title',f"chore: add HDPV2/IKP templates for {app}", '--body-file', 'PR_BODY.md','--base',branch,'--head',new_branch], cwd=workdir)

                else:

                    print('gh not found; please create PR manually')

 

    if args.tmpdir is None:

        print('Leaving tempdir for inspection:', tmpdir)

 

if __name__ == '__main__':

    main()