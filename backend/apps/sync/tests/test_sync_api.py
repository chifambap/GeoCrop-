from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class SyncStatusAPITests(APITestCase):
    """Smoke tests for /api/sync/status/ — auth and happy path."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='sync_tester',
            email='sync_tester@example.com',
            password='test-pass-123',
        )

    def test_status_requires_authentication(self):
        res = self.client.get('/api/sync/status/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_ok_when_authenticated(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get('/api/sync/status/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data.get('ok'))
        self.assertEqual(res.data.get('user'), 'sync_tester')
        self.assertEqual(res.data.get('role'), 'collector')
