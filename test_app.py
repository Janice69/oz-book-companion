"""API validation tests with a stub model; real model checks are separate."""
import unittest

from fastapi.testclient import TestClient

import app as server


class FakeRAG:
    def answer(self, question):
        return {"answer": "Kansas", "sources": [{"id": "passage-0001", "chapter": "Chapter I", "title": "The Cyclone", "text": "Dorothy lived in Kansas."}], "answered": True}


class APITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)
        self.previous = server.engine, server.status
        server.engine, server.status = FakeRAG(), "ready"

    def tearDown(self):
        server.engine, server.status = self.previous

    def test_question_and_sources(self):
        response = self.client.post("/api/chat", json={"question": "Where does Dorothy live?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Kansas")
        self.assertEqual(response.json()["sources"][0]["chapter"], "Chapter I")

    def test_blank_and_oversize(self):
        self.assertEqual(self.client.post("/api/chat", json={"question": "   "}).status_code, 400)
        self.assertEqual(self.client.post("/api/chat", json={"question": "x" * 1001}).status_code, 422)

    def test_loading(self):
        server.status = "loading"
        self.assertEqual(self.client.post("/api/chat", json={"question": "Dorothy?"}).status_code, 503)

    def test_busy(self):
        server.generation_lock.acquire()
        try:
            self.assertEqual(self.client.post("/api/chat", json={"question": "Dorothy?"}).status_code, 429)
        finally:
            server.generation_lock.release()

    def test_frontend_assets(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        for path in ("/static/chat.js", "/static/style.css"):
            self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
