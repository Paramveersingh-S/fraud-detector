from locust import HttpUser, task, between

class ScoringUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def score(self):
        self.client.post("/v1/score", json={
            "transaction_id": "t1", "transaction_dt": 1000.0,
            "transaction_amt": 25.0, "card1": 1, "card2": 1, "card3": 1, "card5": 1, "addr1": 1,
        })
