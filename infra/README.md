# infra

Tout ce qui fait tourner le projet en production, decrit en fichiers.

- `caddy/` : le serveur en frontal, HTTPS automatique.
- `prometheus/` : collecte des mesures techniques.
- `grafana/dashboards/` : tableaux de bord, exportes en JSON.
- `ansible/` : installation et configuration du VPS, rejouables a l'identique.
- `protection-main.json` : les regles de protection de la branche `main`, versionnees pour pouvoir
  les remettre a l'identique apres une intervention d'urgence. Voir
  `docs/commandes/08-depannage.md`.
