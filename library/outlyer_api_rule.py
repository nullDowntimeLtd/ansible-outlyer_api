# Ansible module that manages Outlyer rules (alerts) via the api

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import json
import hashlib

def get_api_url(module, restype):
    ''' Takes ansible module object, and api resource type (agents, rules, etc.) returns api url'''
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


def check_rule_exists(module):
    api_url = get_api_url(module, 'rules')
    headers = get_headers(module)

    resp = requests.get(
        api_url,
        headers=headers
    )

    out = {'found': False, 'error': False, 'data': None}

    if resp.status_code == 200:

        for rule in resp.json():
            if rule['title'] == module.params['rule_name']:
                out['found'] = True
                out['data'] = rule
                break

    elif resp.status_code not in [200, 404]:
        resp.raise_for_status()
        out['error'] = True

    return out


def create_rule(module):
    api_url = get_api_url(module, 'rules')
    headers = get_headers(module)
    data = module.params['rule_content']

    resp = requests.post(
        api_url,
        headers=headers,
        data=data
    )

    resp.raise_for_status()

    return resp


def update_rule(module, rl):
    api_url = get_api_url(module,'rules/%s' % rl['data']['id'])
    headers = get_headers(module)
    data = module.params['rule_content']

    resp = requests.put(
        api_url,
        headers=headers,
        data=data
    )

    resp.raise_for_status()

    return resp


def rm_rule(module, rl):
    api_url = get_api_url(module,'rules/%s' % rl['data']['id'])
    headers = get_headers(module)

    resp = requests.delete(
        api_url,
        headers=headers
    )

    resp.raise_for_status()
    return resp


def get_ol_rule(module,rl):
        api_url = get_api_url(module,'rules/%s' % rl['data']['id'])
        headers = get_headers(module)

        resp = requests.get(
            api_url,
            headers=headers
        )

        resp.raise_for_status()
        return resp.json()


def compare_rules(module,rl):
    params_rule_json = json.loads(module.params['rule_content'])
    ol_rule_json = get_ol_rule(module,rl)

    # We need a fairly extensive preprocessing here, as inputs and outputs have some major differences.
    # Plus unicode fun.
    for d in ol_rule_json['actions']:
        if u'id' in d:
            del d[u'id']

    for d in ol_rule_json['criteria']:
        if u'id' in d:
            del d[u'id']
        if u'data_type' in d:
            del d[u'data_type']
        if u'rule' in d:
            del d[u'rule']
        if u'state' in d:
            del d[u'state']
        if u'sources' in d:
            del d[u'sources']
        if u'scopes' in d:
            d[u'scope'] = dict( tag = d[u'scopes'][0][u'id'] )
            del d[u'scopes']

    # We only compare selected sections as actual rule has a few more than we ever send
    if (    ol_rule_json['title'] != params_rule_json['title']
            or ol_rule_json['description'] != params_rule_json['description']
            or ol_rule_json['actions'] != params_rule_json['actions']
            or ol_rule_json['criteria'] != params_rule_json['criteria']
        ):
        return False
    else:
        return True

def main():
    argument_spec = dict(
        url=dict(required=True),
        org=dict(required=True),
        account=dict(required=True),
        apikey=dict(required=True, no_log=True),
        rule_name=dict(required=True),
        rule_content=dict(required=False, type='jsonarg'),
        state=dict(required=False, default='present', choices=['present', 'absent'])
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_REQUESTS:
        module.fail_json(msg='requests python module is required for this module to work')

    try:
        rl = check_rule_exists(module)
    except requests.exceptions.RequestException, err_str:
        module.fail_json(msg='Request to check rule existence failed', reason=err_str)

    # DEBUG
    ###module.fail_json(msg=rl)

    changed = False
    msg = []

    if module.params['state'] == 'present':
        if rl['found']:
            if not compare_rules(module,rl):
                ur = update_rule(module, rl)
                if ur:
                    changed = True
                    msg.append('rule updated')
            else:
                msg.append('no need to update rule')
        else:
            if not module.params['rule_content']:
                module.fail_json(msg='`rule_content` is required to create new rule')

            cr = create_rule(module)
            if cr:
                changed = True
                msg.append('rule created')
    else:
        if rl['found']:
            try:
                rm_rule(module, rl)
                msg.append('rule deleted')
                changed = True
            except requests.exceptions.RequestException, err_str:
                module.fail_json(msg='Request to delete rule failed', reason=err_str)
        else:
            msg.append('rule not found')

    module.exit_json(changed=changed, msg=msg)


# import module snippets
from ansible.module_utils.basic import *

main()
