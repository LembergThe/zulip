# Fetch a development API key

{generate_api_description(/dev_fetch_api_key:post)}

## Usage examples

{start_tabs}
{tab|curl}

{generate_code_example(curl)|/dev_fetch_api_key:post|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/dev_fetch_api_key:post}

## Response

#### Return values

* `api_key`: The API key that can be used to authenticate as the requested
    user.
* `email`: The email address of the user who owns the API key.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/dev_fetch_api_key:post|fixture(200)}
