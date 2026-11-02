"""Unit-only diagnostic binding. Mock executors never constitute engine measurements."""
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import query_tool
from src.dataset.model import DataError

class PlanBindingTests(unittest.TestCase):
    def test_explain_optional_file_reuses_full_source_verifier(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-plan-binding-') as folder:
            output=Path(folder)/'SYNTHETIC-plan.json'
            executor=MagicMock();executor.execute.return_value={'engine':'postgres','query':'Q1','variant':'default','preflight':{'count':100},'effective':{'server_version':'SYNTHETIC UNIT'},'plan':[{'Plan':{'Node Type':'Seq Scan'}}]}
            binding={'status':'ok','mode':'full','source_sha256':'f'*64}
            with patch.object(query_tool,'QueryExecutor',return_value=executor),patch.object(query_tool,'validate_file',return_value={'sha256':'f'*64}) as check,patch.object(query_tool,'compare_dataset',return_value=binding) as compare,contextlib.redirect_stdout(io.StringIO()):
                rc=query_tool.main(['explain','--engine','postgres','--query','Q1','--file','SYNTHETIC-source.jsonl','--report',str(output)])
            self.assertEqual(rc,0)
            result=json.loads(output.read_text());self.assertEqual(result['dataset_sha256'],'f'*64);self.assertEqual(result['dataset_binding'],binding)
            check.assert_called_once_with('SYNTHETIC-source.jsonl');compare.assert_called_once_with([executor.adapter],'SYNTHETIC-source.jsonl')
            self.assertTrue(executor.execute.call_args.kwargs['explain'])
    def test_source_mismatch_blocks_before_diagnostic_execution(self):
        executor=MagicMock()
        with patch.object(query_tool,'QueryExecutor',return_value=executor),patch.object(query_tool,'validate_file',return_value={'sha256':'f'*64}),patch.object(query_tool,'compare_dataset',side_effect=DataError('SYNTHETIC mismatch')),contextlib.redirect_stdout(io.StringIO()) as out:
            rc=query_tool.main(['explain','--engine','postgres','--query','Q1','--file','SYNTHETIC-source.jsonl'])
        self.assertEqual(rc,2);executor.execute.assert_not_called();self.assertEqual(json.loads(out.getvalue())['status'],'BLOCKED')
