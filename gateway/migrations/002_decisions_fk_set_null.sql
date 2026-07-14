-- Nodes come and go (registration/deregistration is routine), but decision
-- history is the seed of future demand analytics and must survive a node
-- leaving. The original FKs defaulted to NO ACTION, which made DELETE
-- /nodes/{id} 500 once a node had ever been chosen for a real request.

alter table decisions drop constraint decisions_chosen_node_fkey;
alter table decisions add constraint decisions_chosen_node_fkey
  foreign key (chosen_node) references nodes(id) on delete set null;

alter table decisions drop constraint decisions_runner_up_fkey;
alter table decisions add constraint decisions_runner_up_fkey
  foreign key (runner_up) references nodes(id) on delete set null;
