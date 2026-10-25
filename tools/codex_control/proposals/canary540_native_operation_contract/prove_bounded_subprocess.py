import importlib.util,os,sys,time,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('bounded_child',Path(__file__).with_name('bounded_subprocess.PROPOSED.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Proof(unittest.TestCase):
 def command(self,code):return [sys.executable,'-I','-B','-c',code]
 def test_real_child_bounded_roundtrip_and_auth_environment_absent(self):
  name='BISON_KEY';previous=os.environ.get(name)
  try:
   os.environ[name]='synthetic-never-export'
   code="import os,sys; assert 'BISON_KEY' not in os.environ; sys.stdout.buffer.write(sys.stdin.buffer.read())"
   self.assertEqual(m.run_trusted_child(self.command(code),b'synthetic-input',timeout_seconds=5),b'synthetic-input')
  finally:
   if previous is None:os.environ.pop(name,None)
   else:os.environ[name]=previous
 def test_real_sleeping_child_deadline_kills_and_reaps(self):
  started=time.monotonic()
  with self.assertRaises(m.ChildRefused) as failure:m.run_trusted_child(self.command('import time; time.sleep(10)'),timeout_seconds=0.2)
  self.assertTrue(failure.exception.reaped);self.assertLess(time.monotonic()-started,3)
 def test_real_oversize_and_nonzero_are_refused_not_returned(self):
  for code in ["import sys; sys.stdout.buffer.write(b'x'*100000)","raise SystemExit(7)"]:
   with self.assertRaises(m.ChildRefused) as failure:m.run_trusted_child(self.command(code),timeout_seconds=5,max_stdout=1024)
   self.assertTrue(failure.exception.reaped)
 def test_input_contract_rejects_before_process(self):
  for kw in [dict(timeout_seconds=True),dict(timeout_seconds=31),dict(max_stdout=True),dict(payload=b'x'*65537)]:
   with self.assertRaises(m.ChildRefused):m.run_trusted_child(self.command('pass'),**kw)
 def test_thread_start_failure_kills_and_reaps_launched_process(self):
  from unittest import mock
  original=m.subprocess.Popen;original_start=m.threading.Thread.start
  for fail_at in [1,2]:
   processes=[];calls=[0]
   def launch(*a,**kw):
    proc=original(*a,**kw);processes.append(proc);return proc
   def start(thread):
    calls[0]+=1
    if calls[0]==fail_at:raise RuntimeError('synthetic thread exhaustion')
    return original_start(thread)
   with mock.patch.object(m.subprocess,'Popen',side_effect=launch),mock.patch.object(m.threading.Thread,'start',new=start):
    with self.assertRaises(RuntimeError):m.run_trusted_child(self.command('import time;time.sleep(10)'),timeout_seconds=5)
   self.assertEqual(len(processes),1);self.assertIsNotNone(processes[0].poll())
if __name__=='__main__':unittest.main()
