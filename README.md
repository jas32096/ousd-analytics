Vault Eagle

## The Vault Eagle Concept

- Provide easy visibility into the past and current state of OUSD.
- Provide an easy place to get data to make future predictions
- Have early detection when OUSD is becoming unsafe from a changing environment.
- Provide automated alerting when a problem happens.

## Setup

    # Let's create a new virtual environment
    python3 -m venv eagle-python
    source ./eagle-python/bin/activate
    pip install -r eagleproject/requirements.txt
    cd eagleproject
    cp eagleproject/.env.dev eagleproject/.env
    # edit eagleproject/.env and add in your provider URL
    python manage.py migrate

## To run
    export PROVIDER_URL="https://CHANGEURLHERE"
    source ./eagle-python/bin/activate
    python ./manage.py runserver
    # To download data from the blockchain, visit
    # vist http://localhost:9001/reload


## Future

Data ingest:

- Oracle readings
- Actual exchange asset pricing
- Compound state

Views:

- Holdings (current and historical)
- [later] Oracle analysis
- [later] Compound health analysis
- [later] Flagged Transactions

Pushes:

- [later] To Discord

