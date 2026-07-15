-- Registration no longer requires a shared X-Common-Secret (the network is
-- meant to be permissionless -- see README "Scope"). Each node instead gets
-- its own random deregistration token at registration time, returned once
-- in the POST /nodes response and never exposed via GET /nodes, so a node
-- can only be removed by whoever holds its token (or by the health checker).
alter table nodes add column if not exists node_token text
  default encode(gen_random_bytes(24), 'hex') not null;
