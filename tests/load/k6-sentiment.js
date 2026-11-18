import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 20,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<200'],
    http_req_failed: ['rate<0.01'],
  },
};

const URL = __ENV.API_URL || 'http://127.0.0.1:8088/predict';
const PAYLOAD = JSON.stringify({
  texts: [
    'Production MLOps pipeline with ArgoCD and Prometheus is rock solid',
    'Latency spike detected in legacy inference endpoint',
  ],
});

export default function () {
  const res = http.post(URL, PAYLOAD, {
    headers: { 'Content-Type': 'application/json' },
  });
  check(res, {
    'status is 200': (r) => r.status === 200,
    'has predictions': (r) => JSON.parse(r.body).predictions.length === 2,
  });
  sleep(0.1);
}
