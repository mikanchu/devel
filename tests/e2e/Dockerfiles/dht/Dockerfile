FROM bitdust/base

RUN bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441"

ENTRYPOINT ["/root/.bitdust/venv/bin/python", "dht/dht_service.py"]
