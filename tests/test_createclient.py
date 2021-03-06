"""
<copyright
notice="lm-source-program"
pids="5724-H72"
years="2013,2016"
crc="1556180583" >
Licensed Materials - Property of IBM

5725-P60

(C) Copyright IBM Corp. 2013, 2016

US Government Users Restricted Rights - Use, duplication or
disclosure restricted by GSA ADP Schedule Contract with
IBM Corp.
</copyright>
"""
# pylint: disable=bare-except,broad-except,invalid-name,no-self-use
# pylint: disable=too-many-public-methods,unused-argument
import unittest
import pytest
import threading
import re
import inspect
import os
import mqlight
from mqlight.exceptions import SecurityError, InvalidArgumentError


class TestCreateClient(unittest.TestCase):

    """
    Unit tests for Client()
    """
    TEST_TIMEOUT = 10.0

    def test_golden_path(self):
        """
        Test the folden path through using a client
        """
        test_is_done = threading.Event()
        client_id = 'test_golden_path'
        service = 'amqp://host:1234'

        def started(client):
            """started listener"""
            assert client.get_state() == mqlight.STARTED
            assert client.get_service() == service
            client.stop()
            test_is_done.set()

        client = mqlight.Client(
            service=service,
            client_id=client_id,
            on_started=started)
        test_is_done.wait(self.TEST_TIMEOUT)
        assert test_is_done.is_set()

    def test_service_not_a_string(self):
        """
        Test that a service name must be a string
        """
        with pytest.raises(InvalidArgumentError) as exc:
            mqlight.Client(1234)
        assert str(exc.value) == 'Service is an unsupported type','Error: {0}'.format(exc.value)

    def test_create_client_must_have_a_value(self):
        """
        Test that passing no value to create_client is not valid
        """
        # pylint: disable=no-value-for-parameter
        with pytest.raises(TypeError):
            mqlight.Client()

    def test_create_client_callback_must_be_function(self):
        """
        Test that only a function() is accepted as the callback argument
        """
        with pytest.raises(TypeError):
            mqlight.Client('amqp://host:1234', callback=1)

    def test_create_client_must_have_service_value(self):
        """
        Test that omitting the 'service' property from createClient causes an
        error
        """
        # pylint: disable=no-value-for-parameter
        with pytest.raises(TypeError):
            mqlight.Client(
                client_id='test_create_client_must_have_service_value')

    def test_id_types_values(self):
        """
        Test a range of types / values for client IDs
        """
        data = [
            {'data': 1234, 'valid': True},
            {'data': None, 'valid': True},
            {'data': True, 'valid': True},
            {'data': 'abc1234', 'valid': True},
            {'data': ':1234', 'valid': False},
            {'data': '1234:', 'valid': False},
            {'data': '12:34', 'valid': False},
            {'data': '%./_', 'valid': True},
            {'data': '&.\\_', 'valid': False}
        ]
        def stop_client(client):
            client.stop()
        for i in data:
            client = None
            try:
                client = mqlight.Client('amqp://localhost:5672', i['data'], on_started=stop_client)
            except Exception as exc:
                if i['valid']:
                    pytest.fail('Unexpected Exception ' + str(exc))
            finally:
                if client:
                    client.stop()

    def test_id_autogenerated(self):
        """
        Test that if the 'id' property is omitted then the client id will be
        generated
        """
        def stop_client(client):
            client.stop()
        client = mqlight.Client('amqp://localhost:5672',
                                on_started=stop_client)
        assert re.search(r'^AUTO_[a-z0-9%/._]{7}$',
                         client.get_id()) is not None
        #client.stop()

    def test_user_password_types_values(self):
        """
        Test a range of user and password types / values
        """
        data = [
            {'user': 'abc', 'password': None, 'valid': False},
            {'user': None, 'password': 'abc', 'valid': False},
            {'user': 'abc', 'password': '123', 'valid': True},
            {'user': 1234, 'password': 'abc', 'valid': False},
            {'user': 'abc', 'password': 1234, 'valid': False},
            {
                'user': '!"$%^&*()-_=+[{]};:\'@#~|<,>.?/',
                'password': '!"$%^&*()-_=+[{]};:\'@#~|<,>.?/',
                'valid': True
            }
        ]
        for i in range(len(data)):
            opts = data[i]
            security_options = {
                'user': opts['user'],
                'password': opts['password']
            }
            client = None
            try:
                def stop_client(client):
                    client.stop()
                client = mqlight.Client('amqp://localhost:5672',
                                        'id' + str(i),
                                        security_options,
                                        on_started=stop_client)
            except Exception as exc:
                if opts['valid']:
                    pytest.fail('Unexpected Exception ' + str(exc))
            finally:
                if client:
                    client.stop()

    def test_password_hidden(self):
        """
        Test that a clear text password isn't trivially recoverable from the
        client object
        """
        def stop_client(client):
            client.stop()
        client = mqlight.Client('amqp://localhost:5672',
                                'test_password_hidden',
                                {'user': 'username',
                                 'password': 's3cret'},
                                on_started=stop_client)
        members = inspect.getmembers(client,
                                     lambda a: not inspect.isroutine(a))
        assert re.search(r's3cret', str(members)) is None

    def test_valid_uris(self):
        """
        Test that the value returned by client.get_service is a lower cased URL
        which always has a port number
        """
        test_is_done = threading.Event()
        data = [
            {'uri': 'amqp://host', 'expected': 'amqp://host:5672'},
            {'uri': 'amqps://host', 'expected': 'amqps://host:5671'},
            {'uri': 'AmQp://HoSt', 'expected': 'amqp://host:5672'},
            {'uri': 'aMqPs://hOsT', 'expected': 'amqps://host:5671'},
            {'uri': 'amqp://host:1234', 'expected': 'amqp://host:1234'},
            {'uri': 'amqps://host:4321', 'expected': 'amqps://host:4321'},
            {'uri': 'aMqP://HoSt:1234', 'expected': 'amqp://host:1234'},
            {'uri': 'AmQpS://hOsT:4321', 'expected': 'amqps://host:4321'}
        ]
        clients = []
        count = 0
        for opts in data:
            started_event = threading.Event()

            def started(client):
                """started listener"""
                started_event.set()  # pylint: disable=cell-var-from-loop
            clients.append(mqlight.Client(
                service=opts['uri'],
                client_id=str(count),
                on_started=started))
            started_event.wait(2.0)
            assert started_event.is_set()
            count += 1
            if count == len(data):
                test_is_done.set()
        test_is_done.wait(self.TEST_TIMEOUT)
        assert test_is_done.is_set()
        for client in clients:
            expected_service = data[int(client.get_id())]['expected']
            assert client.get_service() == expected_service, 'Actual {0} service'.format(client.get_service())
            client.stop()

    def test_bad_ssl_options(self):
        """
        Test that bad ssl options cause Client to fail
        """
        data = [
            {'ssl_trust_certificate': 1, 'ssl_verify_name': True},
            {'ssl_trust_certificate': {'a': 1}, 'ssl_verify_name': True},
            {'ssl_trust_certificate': True, 'ssl_verify_name': True},
            {
                'ssl_trust_certificate': 'ValidCertificate',
                'ssl_verify_name': 'a'
            },
            {
                'ssl_trust_certificate': 'ValidCertificate',
                'ssl_verify_name': '1'
            },
            {
                'ssl_trust_certificate': 'ValidCertificate',
                'ssl_verify_name': {'a': 1}
            },
        ]
        for i, option in enumerate(data):
            with pytest.raises(Exception) as err:
                service = 'amqp://host'
                client_id = 'test_bad_ssl_options_{0}'.format(i)
                security_options = option
                mqlight.Client(service, client_id, security_options)
            err_type = type(err.value)
            allowed = err_type in (TypeError,
                                   SecurityError,
                                   InvalidArgumentError)
            assert allowed, 'errtype is unexpectedly ' + str(err_type)
        if os.path.exists('dirCertificate'):
            os.rmdir('dirCertificate')

    def test_valid_ssl_options(self):
        """
        Test that the ssl options for valid certificates cause start to be
        successful
        """
        test_is_done = threading.Event()
        data = [
            {
                'ssl_trust_certificate': 'ValidCertificate',
                'ssl_verify_name': True
            },
            {
                'ssl_trust_certificate': 'ValidCertificate',
                'ssl_verify_name': True
            },
            {
                'ssl_trust_certificate': 'BadVerify',
                'ssl_verify_name': False
            }
        ]
        valid_certificate_fd = open('ValidCertificate', 'w')
        bad_verify_fd = open('BadVerify', 'w')

        def valid_ssl_test(ssl_trust_certificate, ssl_verify_name):
            """test runner"""
            service = 'amqp://host'
            client_id = 'test_valid_ssl_options'
            security_options = {
                'ssl_trust_certificate': ssl_trust_certificate,
                'ssl_verify_name': ssl_verify_name
            }

            def state_changed(client, state, err):
                if state == mqlight.ERROR:
                    """error listener"""
                    pytest.fail('Unexpected error event: ' + str(err))
                    client.stop()
                    valid_certificate_fd.close()
                    os.remove('ValidCertificate')
                    bad_verify_fd.close()
                    os.remove('BadVerify')
                    test_is_done.set()

            def stopped(client, err):
                """stopped listener"""
                if len(data) == 0:
                    valid_certificate_fd.close()
                    os.remove('ValidCertificate')
                    bad_verify_fd.close()
                    os.remove('BadVerify')
                    test_is_done.set()
                else:
                    ssl_data = data.pop()
                    valid_ssl_test(ssl_data['ssl_trust_certificate'],
                                   ssl_data['ssl_verify_name'])

            def started(client):
                """started listener"""
                client.stop(stopped)
            client = mqlight.Client(
                service=service,
                client_id=client_id,
                security_options=security_options,
                on_started=started,
                on_state_changed=state_changed)

        ssl_data = data.pop()
        valid_ssl_test(
            ssl_data['ssl_trust_certificate'],
            ssl_data['ssl_verify_name'])
        test_is_done.wait(self.TEST_TIMEOUT)
        assert test_is_done.is_set()

    def test_invalid_ssl_options(self):
        """
        Test that the ssl options for invalid certificates cause start to fail
        """
        test_is_done = threading.Event()
        data = [
            {
                'ssl_trust_certificate': 'BadCertificate',
                'ssl_verify_name': True
            },
            {
                'ssl_trust_certificate': 'BadCertificate',
                'ssl_verify_name': False
            },
            {
                'ssl_trust_certificate': 'BadVerify2',
                'ssl_verify_name': True
            }
        ]
        bad_certificate_fd = open('BadCertificate', 'w+')
        bad_verify_fd = open('BadVerify2', 'w+')

        def invalid_ssl_test(ssl_trust_certificate, ssl_verify_name):
            """test runner"""
            service = 'amqp://host'
            client_id = 'test_invalid_ssl_options'
            security_options = {
                'ssl_trust_certificate': ssl_trust_certificate,
                'ssl_verify_name': ssl_verify_name
            }

            def state_changed(client, state, err):
                if state == mqlight.STOPPED:
                    stopped(client)

            def stopped(client):
                """stopped listener"""
                if len(data) == 0:
                    test_is_done.set()
                else:
                    ssl_data = data.pop()
                    invalid_ssl_test(ssl_data['ssl_trust_certificate'],
                                     ssl_data['ssl_verify_name'])

            def started(client):
                """started listener"""
                client.stop()
                bad_certificate_fd.close()
                os.remove('BadCertificate')
                bad_verify_fd.close()
                os.remove('BadVerify2')
                pytest.fail('unexpected started event' + str(security_options))
                test_is_done.set()
            client = mqlight.Client(
                service=service,
                client_id=client_id,
                security_options=security_options,
                on_started=started,
                on_state_changed=state_changed)

        ssl_data = data.pop()
        invalid_ssl_test(ssl_data['ssl_trust_certificate'],
                         ssl_data['ssl_verify_name'])
        test_is_done.wait(self.TEST_TIMEOUT)
        bad_certificate_fd.close()
        os.remove('BadCertificate')
        bad_verify_fd.close()
        os.remove('BadVerify2')
        assert test_is_done.is_set()


    def test_client_id_limit(self):
        """
        Test that you can set the client ID to the maximum limit,
        but no longer than that
        """
        test_is_done = threading.Event()
        client_id = "A"*256
        service = 'amqp://host:1234'

        def started(client):
            """started listener"""
            client.stop()

        with pytest.raises(InvalidArgumentError):
            client = mqlight.Client(
                service=service,
                client_id=client_id+"A")
        client = mqlight.Client(
            service=service,
            client_id=client_id,
            on_started=started)
        test_is_done.set()
        test_is_done.wait(self.TEST_TIMEOUT)
        assert test_is_done.is_set()

if __name__ == 'main':
    unittest.main()
