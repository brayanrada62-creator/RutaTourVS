from django.test import SimpleTestCase


class SwaggerAccessTest(SimpleTestCase):
    def test_swagger_is_available_without_authentication(self):
        response = self.client.get('/swagger/')

        self.assertEqual(response.status_code, 200)
