# Ansible module that manages Outlyer plugins via the api

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import json
import base64
import hashlib

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


def check_plugin_exists(module):
    api_url = get_api_url(module, 'plugins')
    headers = get_headers(module)

    resp = requests.get(
        api_url,
        headers=headers
    )

    out = {'found': False, 'error': False, 'data': None}

    if resp.status_code == 200:

        for plugin in resp.json():
            if plugin['name'] == module.params['plugin_name'] and plugin['extension'] == module.params['extension']:
                out['found'] = True
                out['data'] = plugin
                break

    elif resp.status_code not in [200, 404]:
        resp.raise_for_status()
        out['error'] = True

    return out

def create_plugin(module):
    api_url = get_api_url(module, 'plugins')
    headers = get_headers(module)
    data = {
        "name": module.params['plugin_name'],
        "description": module.params['description'],
        "content": module.params['plugin_content'],
        #"type": module.params['type'],
        "extension": module.params['extension']
    }

    resp = requests.post(
        api_url,
        headers=headers,
        data=json.dumps(data)
    )

    resp.raise_for_status()

    return resp

def update_plugin(module, pl):
    api_url = get_api_url(module,'plugins/%s' % pl['data']['id'])
    headers = get_headers(module)

    data = {
        #"name": np['data']['name'],
        #"description": np['data']['description'],
        #"extension": np['data']['extension'],
        "content": module.params['plugin_content']
    }

    resp = requests.patch(
        api_url,
        headers=headers,
        data=json.dumps(data)
    )

    resp.raise_for_status()

    return resp

def rm_plugin(module, pl):
    api_url = get_api_url(module,'plugins/%s' % pl['data']['id'])
    headers = get_headers(module)

    resp = requests.delete(
        api_url,
        headers=headers
    )

    resp.raise_for_status()
    return resp

def get_dl_plugin_sha(module,pl):
        api_url = get_api_url(module,'plugins/%s' % pl['data']['id'])
        headers = get_headers(module)

        resp = requests.get(
            api_url,
            headers=headers
        )

        resp.raise_for_status()
        sha = hashlib.sha1()
        sha.update(resp.json()['content'])
        ##module.fail_json(msg=sha.hexdigest())
        return sha

def main():
    argument_spec = dict(
        url=dict(required=True),
        org=dict(required=True),
        account=dict(required=True),
        apikey=dict(required=True, no_log=True),
        plugin_name=dict(required=True),
        plugin_content=dict(required=False),
        description=dict(required=False,default='bad practice'),
        type=dict(required=False,default='script'),
        extension=dict(required=False, default='py'),
        state=dict(required=False, default='present', choices=['present', 'absent'])
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_REQUESTS:
        module.fail_json(msg='requests python module is required for this module to work')

    try:
        pl = check_plugin_exists(module)
    except requests.exceptions.RequestException, err_str:
        module.fail_json(msg='Request to check plugin existence failed', reason=err_str)

    # DEBUG
    ###module.fail_json(msg=pl)

    changed = False
    msg = []

    if module.params['state'] == 'present':
        if pl['found']:
            content_sha = hashlib.sha1()
            #content_sha.update(base64.b64decode(module.params['plugin_content']))
            content_sha.update(module.params['plugin_content'])
            dl_content_sha = get_dl_plugin_sha(module,pl)
            if dl_content_sha.hexdigest() != content_sha.hexdigest():
                up = update_plugin(module, pl)
                if up:
                    changed = True
                    msg.append('plugin updated')
            else:
                msg.append('no need to update plugin')
        else:
            if not module.params['plugin_content']:
                module.fail_json(msg='`plugin_content` is required to create new plugin')
                
            cp = create_plugin(module)
            if cp:
                changed = True
                msg.append('plugin created')
    else:
        if pl['found']:
            try:
                rm_plugin(module, pl)
                msg.append('plugin deleted')
                changed = True
            except requests.exceptions.RequestException, err_str:
                module.fail_json(msg='Request to delete plugin failed', reason=err_str)
        else:
            msg.append('plugin not found')

    module.exit_json(changed=changed, msg=msg)


# import module snippets
from ansible.module_utils.basic import *

main()
