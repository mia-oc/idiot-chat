import unittest

from idiot_chat.session import Session


class SessionTests(unittest.TestCase):
    def test_requires_explicit_start_and_stop_invalidates_work(self):
        session = Session()
        self.assertFalse(session.active)
        with self.assertRaises(RuntimeError):
            session.token()
        first = session.start()
        self.assertTrue(session.current(first))
        session.stop()
        self.assertTrue(first.is_set())
        self.assertFalse(session.current(first))
        with self.assertRaises(RuntimeError):
            session.token()
        second = session.start()
        self.assertIsNot(first, second)
        self.assertFalse(session.current(first))
        self.assertTrue(session.current(second))

    def test_start_invalidates_any_previous_session(self):
        session = Session()
        first = session.start()
        second = session.start()
        self.assertTrue(first.is_set())
        self.assertTrue(session.current(second))


if __name__ == '__main__':
    unittest.main()
