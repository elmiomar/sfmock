# sfmock

Mock service to replace Salesforce service during unit tests.


Requires: Python 3.x

## Run

Set sender email info:

```sh
export GMAIL_USER=...
export GMAIL_PASSWORD=...
```

Run the app:

```sh
uvicorn app:app --reload
```