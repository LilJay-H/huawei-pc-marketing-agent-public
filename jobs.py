"""Small single-worker queue for long model requests; no account or daily quota."""
from collections import OrderedDict
from queue import Queue
import threading
import time
import uuid


class JobQueue:
    def __init__(self, capacity=8, retained=20, ttl=1800):
        self.capacity, self.retained, self.ttl = capacity, retained, ttl
        self.jobs = OrderedDict()
        self.lock = threading.Lock()
        self.pending = Queue()
        self.worker = None

    def prune(self):
        completed = [key for key, job in self.jobs.items() if job['status'] == 'completed']
        for key in completed:
            if time.monotonic() - self.jobs[key]['finished'] > self.ttl:
                del self.jobs[key]
        completed = [key for key, job in self.jobs.items() if job['status'] == 'completed']
        for key in completed[:-self.retained]:
            del self.jobs[key]

    def submit(self, work):
        with self.lock:
            self.prune()
            if sum(job['status'] != 'completed' for job in self.jobs.values()) >= self.capacity:
                raise RuntimeError('当前等待任务较多，请稍后再试。没有扣除每日额度，也未开始本次模型调用。')
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = {'status': 'queued'}
            self.pending.put((job_id, work))
            if self.worker is None:
                self.worker = threading.Thread(target=self.run, daemon=True, name='campus-generation')
                self.worker.start()
            return job_id

    def read(self, job_id):
        with self.lock:
            self.prune()
            job = self.jobs.get(job_id)
            if job is None:
                return None
            if job['status'] == 'completed':
                return {'job_id': job_id, 'status': 'completed', 'result': job['result']}
            ahead = 0
            for key, candidate in self.jobs.items():
                if key == job_id:
                    break
                ahead += candidate['status'] != 'completed'
            return {'job_id': job_id, 'status': job['status'], 'ahead': ahead}

    def run(self):
        while True:
            job_id, work = self.pending.get()
            with self.lock:
                self.jobs[job_id]['status'] = 'running'
            try:
                result = work()
            except Exception:
                # Never echo provider errors, credentials or local filesystem paths.
                result = {'status': 'failed', 'error': '服务处理失败，请稍后重试。'}
            with self.lock:
                self.jobs[job_id] = {'status': 'completed', 'result': result, 'finished': time.monotonic()}
                self.prune()
            self.pending.task_done()
