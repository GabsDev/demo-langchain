# Specs — Restaurante Bot

> **Convención (obligatoria):** todos los specs de este proyecto viven en esta
> carpeta `specs/`, dentro de `restaurante-bot/`. No crear specs fuera de aquí
> (ni en `openspec/` de la raíz del workspace, que pertenece a otros proyectos).

## Documentos

| Archivo | Contenido | Estado |
|---|---|---|
| [`produccion.md`](./produccion.md) | TODOs y decisiones para llevar la POC a producción (incl. decisión de ambientes: local + prod, sin staging) | Borrador |
| [`deploy.md`](./deploy.md) | Roadmap de deploy gratis (Oracle Always Free) para compartir con un cliente | Borrador |

## Convención

1. **Ubicación:** cada spec nuevo → `restaurante-bot/specs/<nombre>.md`.
2. **Idioma:** español (neutral/profesional) para el contenido; el código de
   referencia siempre en inglés.
3. **Formato:** al iniciar un spec nuevo, agregar fila a la tabla de este
   índice y mantenerla al día.
4. **Estado:** `Borrador` → `Aprobado` → `Implementado` → `Archivado`.
5. Si un spec cubre varios temas (p. ej. producción y API), separar por
   secciones dentro del mismo archivo o crear subcarpetas por dominio
   (`specs/produccion/`, `specs/api/`, ...) — siempre bajo `restaurante-bot/specs/`.
