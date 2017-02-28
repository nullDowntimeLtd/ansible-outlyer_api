# Ansible module that lists Outlyer agents via the api

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import json

def get_api_url(module, restype):
    ''' Takes ansible module object, and api resource type (links, plugins, etc.) returns api url'''
    url = '%s/orgs/%s/accounts/%s/%s' % (
          module.params['url'],
          module.params['org'],
          module.params['account'],
          restype
    )
    return url

def get_headers(module):
    ''' Takes ansible module object, returns headers for Outlyer api '''
    headers = {
        'Content-Type': "application/json",
        'authorization': "Bearer %s" % module.params['apikey']
    }
    return headers


def list_agents(module):
    ''' Takes ansible module object, returns data for one or all agents '''
    api_url = get_api_url(module, 'agents')
    headers = get_headers(module)

    resp = requests.get(
        api_url,
        headers=headers
    )

    data = None

    if resp.status_code == 200:
        data = resp.json()

    elif resp.status_code not in [200, 404]:
        resp.raise_for_status()

    out = None

    if module.params['hostname']:
        for a in data:
            if a['hostname'] == module.params['hostname']:
                out = a
                break
    elif module.params['tags']:
        tagged_agents = []
        for a in data:
            if set(module.params['tags']).issubset(set(a['tags'])):
                tagged_agents.append(a)

        if len(tagged_agents) > 0 :
            out = tagged_agents

    else:
        out = data

    return out


def main():
    argument_spec = dict(
        url=dict(required=True),
        org=dict(required=True),
        account=dict(required=True),
        apikey=dict(required=True, no_log=True),
        hostname=dict(required=False),
        tags=dict(required=False, type='list')
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_REQUESTS:
        module.fail_json(msg='requests python module is required for this module to work')

    if module.params['hostname'] and module.params['tags']:
        module.fail_json(msg='`hostname` and `tags` parameters are mutually exclusive')

    try:
        agent_data = list_agents(module)
    except requests.exceptions.RequestException, err_str:
        module.fail_json(msg='Request to list agents failed', reason=err_str)

    changed = False

    module.exit_json(changed=changed, agents=agent_data)


from ansible.module_utils.basic import *

main()
