FROM bitdust/base

ENV BITDUST_API_PASS_EXTERNAL_CONNECTIONS=1
ENV BITDUST_GIT_SYNC_SKIP=1

RUN bitdust set services/identity-propagate/known-servers is:8084:6661
RUN bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441"
RUN bitdust set services/proxy-server/enabled true

RUN bitdust set services/proxy-transport/enabled false
RUN bitdust set services/customer/enabled false
RUN bitdust set services/supplier/enabled false

ENTRYPOINT ["bitdust"]
