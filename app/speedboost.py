import requests

r = requests.post(
    "https://api.test.fiindo.com/api/v1/speedboost",
    headers={"Authorization": "Bearer florian.falk"},
    json={"first_name": "florian", "last_name": "falk"},
)
print(r.status_code, r.text)
