# Ansible module that manages Outlyer plugin-to-tag links via the api

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


def check_link_exists(module):
    api_url = get_api_url(module, 'links')
    headers = get_headers(module)

    resp = requests.get(
        api_url,
        headers=headers
    )
    # {
    #     "id": "5899cefc9f4a6e7b49840d7b",
    #     "org": "587f7a8cf48d0d3a7479bcd7",
    #     "plugin": "java",
    #     "tags": [
    #         "java"
    #     ]
    # },

    out = {'found': False, 'complete': False, 'error': False, 'data': None}

    if resp.status_code == 200:

        for link in resp.json():
            if link['plugin'] == module.params['plugin']:
                out['found'] = True
                out['data'] = link
                ###module.fail_json(msg=('link: %s' % link))
                break

        if out['data']:
            c = 0
            for m in module.params['tags']:
                if m in link['tags']:
                    c += 1
            if c == len(module.params['tags']):
                out['complete'] = True

    elif resp.status_code not in [200, 404]:
        resp.raise_for_status()
        out['error'] = True

    return out

def update_link(module, le):
    tags = set()

    for t in module.params['tags']:
        tags.add(t)

    for t in le['data']['tags']:
        tags.add(t)

    module.params['tags'] = list(tags)

    try:
        delete_link(module, le)
    except requests.exceptions.RequestException, err_str:
        module.fail_json(msg='Request to delete link failed', reason=err_str)

    try:
        create_link(module)
    except requests.exceptions.RequestException, err_str:
        module.fail_json(msg='Request to create link failed', reason=err_str)

    return True


def recreate_link(module, le):
    try:
        delete_link(module, le)
    except requests.exceptions.RequestException, err_str:
        module.fail_json(msg='Request to delete link failed', reason=err_str)

    try:
        create_link(module)
    except requests.exceptions.RequestException, err_str:
        module.fail_json(msg='Request to create link failed', reason=err_str)

    return True


def create_link(module):
    api_url = get_api_url(module,'links')
    headers = get_headers(module)
    data = {"plugin": module.params['plugin'], "tags": module.params['tags']}

    resp = requests.post(
        api_url,
        headers=headers,
        data=json.dumps(data)
    )

    resp.raise_for_status()
    return resp


def delete_link(module, le):
    api_url = get_api_url(module,'links/%s' % le['data']['id'])
    headers = get_headers(module)
    data = {"plugin": module.params['plugin'], "tags": module.params['tags']}

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
        plugin=dict(required=True),
        tags=dict(required=True, type='list'),
        replace_tags=dict(required=False, default=False, type='bool'),
        state=dict(required=False, default='present', choices=['present', 'absent'])
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_REQUESTS:
        module.fail_json(msg='requests python module is required for this module to work')

    try:
        le = check_link_exists(module)
    except requests.exceptions.RequestException, err_str:
        module.fail_json(msg='Request to check link existence failed', reason=err_str)

    ##module.fail_json(msg=('le: %s' % le))

    changed = False
    msg = []

    if module.params['state'] == 'present':
        if le['found'] and le['complete']:
            msg.append('link already exists and contains the specified tag(s)')
        elif le['found']:
            # UPDATE link - found but not complete, does not contain the desired tag(s)
            if module.params['replace_tags']:
                rl = recreate_link(module, le)
                if rl:
                    msg.append('link recreated')
                    changed = True
                else:
                    module.fail_json(msg='link update failed')
            else:
                ul = update_link(module, le)
                if ul:
                    msg.append('link updated')
                    changed = True
                else:
                    module.fail_json(msg='link update failed')
        else:
            try:
                create_link(module)
                msg.append('link created')
                changed = True
            except requests.exceptions.RequestException, err_str:
                module.fail_json(msg='Request to create link failed', reason=err_str)
    else:
        if le['found']:
            try:
                delete_link(module, le)
                msg.append('link deleted')
                changed = True
            except requests.exceptions.RequestException, err_str:
                module.fail_json(msg='Request to delete link failed', reason=err_str)
        else:
            msg.append('link not found, nothing to delete')

    module.exit_json(changed=changed, msg=msg)


# import module snippets
from ansible.module_utils.basic import *
#from ansible.module_utils.api import *

main()
