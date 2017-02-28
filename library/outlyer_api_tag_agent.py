# Ansible module that manages Outlyer agent tags via the api

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import json

def get_api_url(module, restype):
    ''' Takes ansible module object, and api resource type (agents, plugins, etc.) returns api url'''
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


def check_agent_exists(module):
    api_url = get_api_url(module, 'agents')
    headers = get_headers(module)

    resp = requests.get(
        api_url,
        headers=headers
    )

    out = {'found': False, 'complete': False, 'error': False, 'data': None}

    if resp.status_code == 200:

        for agent in resp.json():
            if agent['id'] == module.params['agent_id']:
                out['found'] = True
                out['data'] = agent
                break

        if out['data']:
            c = 0
            for m in module.params['tags']:
                if m in agent['tags']:
                    c += 1
            if c == len(module.params['tags']):
                out['complete'] = True

    elif resp.status_code not in [200, 404]:
        resp.raise_for_status()
        out['error'] = True

    return out

def add_agent_tag(module, al, tags_to_add):
    api_url = get_api_url(module,'agents/%s/tags' % al['data']['id'])
    headers = get_headers(module)
    data = {"names": tags_to_add}

    resp = requests.put(
        api_url,
        headers=headers,
        data=json.dumps(data)
    )

    resp.raise_for_status()
    return resp

def rm_agent_tag(module, al, tags_to_remove):
    api_url = get_api_url(module,'agents/%s/tags' % al['data']['id'])
    headers = get_headers(module)
    # Yes, payload is different when tags are being removed...
    data = {"tags": tags_to_remove}

    resp = requests.delete(
        api_url,
        headers=headers,
        data=json.dumps(data)
    )

    resp.raise_for_status()
    return resp


def main():
    argument_spec = dict(
        url=dict(required=True),
        org=dict(required=True),
        account=dict(required=True),
        apikey=dict(required=True, no_log=True),
        agent_id=dict(required=True),
        tags=dict(required=True, type='list'),
        state=dict(required=False, default='present', choices=['present', 'absent'])
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_REQUESTS:
        module.fail_json(msg='requests python module is required for this module to work')

    try:
        al = check_agent_exists(module)
    except requests.exceptions.RequestException, err_str:
        module.fail_json(msg='Request to check agent existence failed', reason=err_str)

    ###module.fail_json(msg=('al: %s' % al))

    changed = False
    msg = []

    if module.params['state'] == 'present':
        if al['found'] and al['complete']:
            msg.append('agent already tagged with the specified tag(s)')
        elif al['found']:
            # UPDATE agent - found but not complete, does not contain the desired tag(s)
            tags_to_add = []
            for t in module.params['tags']:
                if t not in al['data']['tags']:
                    tags_to_add.append(t)

            if len(tags_to_add) > 0:
                try:
                    add_agent_tag(module, al, tags_to_add)
                    msg.append('agent tags updated')
                    changed = True
                except requests.exceptions.RequestException, err_str:
                    module.fail_json(msg='Request to add agent tags failed', reason=err_str)
        else:
            # Agent was specified but not found, it's an error
            module.fail_json(msg='agent not found')
    else:
        if al['found']:
            tags_to_remove = []
            for t in module.params['tags']:
                if t in al['data']['tags']:
                    tags_to_remove.append(t)

            if len(tags_to_remove) > 0:
                try:
                    rm_agent_tag(module, al, tags_to_remove)
                    msg.append('specified agent tags deleted')
                    changed = True
                except requests.exceptions.RequestException, err_str:
                    module.fail_json(msg='Request to delete agent tags failed', reason=err_str)
            else:
                # This agent isn't tagged with specified tags, so there's nothing to do.
                # NOT an error.
                msg.append('specified tags are not assigned to this agent, nothing to delete')
        else:
            # Agent must be specified but was not found, it's an error
            module.fail_json(msg='agent not found')

    module.exit_json(changed=changed, msg=msg)


# import module snippets
from ansible.module_utils.basic import *

main()
