# infra

Tout ce qui fait tourner le projet en production, decrit en fichiers.

- `caddy/` : le serveur en frontal, HTTPS automatique.
- `prometheus/` : collecte des mesures techniques.
- `grafana/dashboards/` : tableaux de bord, exportes en JSON.
- `ansible/` : installation et configuration du VPS, rejouables a l'identique.
