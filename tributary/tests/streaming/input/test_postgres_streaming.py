import tributary.streaming as ts
import pytest


class TestPostgres:
    @pytest.mark.skipif("int(os.environ.get('TRIBUTARY_SKIP_DOCKER_TESTS', '1'))")
    def test_pg(self):
        query = ['SELECT * FROM test']
        out = ts.PostgresSource(queries=query,
                                user='postgres',
                                database='postgres',
                                password='test',
                                host='localhost:5432')
        assert len(ts.run(out)) != 0
