# Infrastructure guidance

- Read root guidance, this README and accepted deployment ADRs first.
- Compose includes the development Speaches GPU service and on-demand host
  validation checks; see ADR 0005. Add other services after their versions,
  resource needs, interfaces and secret handling are decided.
- Keep container configuration here and application code in its owning module.
- Use explicit `environment` or `env_file` mappings when services are added.
  Compose interpolation is not automatic injection into container environments.
- Review volume persistence, migration and rollback for deployment changes.
  Run `docker compose -f infrastructure/compose.yaml config --quiet`.
