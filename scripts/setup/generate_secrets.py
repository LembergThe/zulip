#!/usr/bin/env python3
# This tools generates /etc/zulip/zulip-secrets.conf

import sys
import os

from typing import Dict, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
from scripts.lib.setup_path import setup_path

setup_path()

os.environ['DJANGO_SETTINGS_MODULE'] = 'zproject.settings'

import argparse
import uuid
import configparser

os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))

# Standard, 64-bit tokens
AUTOGENERATED_SETTINGS = [
    'avatar_salt',
    'rabbitmq_password',
    'shared_secret',
    'thumbor_key',
]

def random_string(cnt: int) -> str:
    # We do in-function imports so that we only do the expensive work
    # of importing cryptography modules when necessary.
    #
    # This helps optimize noop provision performance.
    from django.utils.crypto import get_random_string

    return get_random_string(cnt)

def random_token() -> str:
    # We do in-function imports so that we only do the expensive work
    # of importing cryptography modules when necessary.
    #
    # This helps optimize noop provision performance.
    from zerver.lib.utils import generate_random_token

    return generate_random_token(64)

def generate_django_secretkey() -> str:
    """Secret key generation taken from Django's startproject.py"""

    # We do in-function imports so that we only do the expensive work
    # of importing cryptography modules when necessary.
    #
    # This helps optimize noop provision performance.
    from django.utils.crypto import get_random_string

    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    return get_random_string(50, chars)

def get_old_conf(output_filename: str) -> Dict[str, str]:
    if not os.path.exists(output_filename) or os.path.getsize(output_filename) == 0:
        return {}

    secrets_file = configparser.RawConfigParser()
    secrets_file.read(output_filename)

    return dict(secrets_file.items("secrets"))

def generate_secrets(development: bool = False) -> None:
    if development:
        OUTPUT_SETTINGS_FILENAME = "zproject/dev-secrets.conf"
    else:
        OUTPUT_SETTINGS_FILENAME = "/etc/zulip/zulip-secrets.conf"
    current_conf = get_old_conf(OUTPUT_SETTINGS_FILENAME)

    lines: List[str] = []
    if len(current_conf) == 0:
        lines = ['[secrets]\n']

    def need_secret(name: str) -> bool:
        return name not in current_conf

    def add_secret(name: str, value: str) -> None:
        lines.append("%s = %s\n" % (name, value))
        current_conf[name] = value

    for name in AUTOGENERATED_SETTINGS:
        if need_secret(name):
            add_secret(name, random_token())

    # These secrets are exclusive to a Zulip develpment environment.
    # We use postgres peer authentication by default in production,
    # and initial_password_salt is used to generate passwords for the
    # test/development database users.  See `manage.py
    # print_initial_password`.
    if development and need_secret("initial_password_salt"):
        add_secret("initial_password_salt", random_token())
    if development and need_secret("local_database_password"):
        add_secret("local_database_password", random_token())

    # The core Django SECRET_KEY setting, used by Django internally to
    # secure sessions.  If this gets changed, all users will be logged out.
    if need_secret('secret_key'):
        secret_key = generate_django_secretkey()
        add_secret('secret_key', secret_key)
        # To prevent Django ImproperlyConfigured error
        from zproject import settings
        settings.SECRET_KEY = secret_key

    # Secret key for the Camo HTTPS proxy.
    if need_secret('camo_key'):
        add_secret('camo_key', random_string(64))

    if not development:
        # The memcached_password and redis_password secrets are only
        # required/relevant in production.

        # Password for authentication to memcached.
        if need_secret("memcached_password"):
            # We defer importing settings unless we need it, because
            # importing settings is expensive (mostly because of
            # django-auth-ldap) and we want the noop case to be fast.
            from zproject import settings

            if settings.MEMCACHED_LOCATION == "127.0.0.1:11211":
                add_secret("memcached_password", random_token())

        # Password for authentication to redis.
        if need_secret("redis_password"):
            # We defer importing settings unless we need it, because
            # importing settings is expensive (mostly because of
            # django-auth-ldap) and we want the noop case to be fast.
            from zproject import settings

            if settings.REDIS_HOST == "127.0.0.1":
                # To prevent Puppet from restarting Redis, which would lose
                # data because we configured Redis to disable persistence, set
                # the Redis password on the running server and edit the config
                # file directly.

                import redis
                from zerver.lib.redis_utils import get_redis_client

                redis_password = random_token()

                for filename in ["/etc/redis/zuli-redis.conf", "/etc/redis/zulip-redis.conf"]:
                    if os.path.exists(filename):
                        with open(filename, "a") as f:
                            f.write(
                                "# Set a Redis password based on zulip-secrets.conf\n"
                                "requirepass '%s'\n" % (redis_password,)
                            )
                        break

                try:
                    get_redis_client().config_set("requirepass", redis_password)
                except redis.exceptions.ConnectionError:
                    pass

                add_secret("redis_password", redis_password)

    # Random id and secret used to identify this installation when
    # accessing the Zulip mobile push notifications service.
    # * zulip_org_key is generated using os.urandom().
    # * zulip_org_id only needs to be unique, so we use a UUID.
    if need_secret('zulip_org_key'):
        add_secret('zulip_org_key', random_string(64))
    if need_secret('zulip_org_id'):
        add_secret('zulip_org_id', str(uuid.uuid4()))

    if need_secret('postgres_password'):
        add_secret('postgres_password', os.getenv('REMOTE_POSTGRES_PASSWORD'))

    if len(lines) == 0:
        print("generate_secrets: No new secrets to generate.")
        return

    with open(OUTPUT_SETTINGS_FILENAME, 'a') as f:
        # Write a newline at the start, in case there was no newline at
        # the end of the file due to human editing.
        f.write("\n" + "".join(lines))

    print("Generated new secrets in %s." % (OUTPUT_SETTINGS_FILENAME,))

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--development', action='store_true', dest='development',
                       help='For setting up the developer env for zulip')
    group.add_argument('--production', action='store_false', dest='development',
                       help='For setting up the production env for zulip')
    results = parser.parse_args()

    generate_secrets(results.development)
