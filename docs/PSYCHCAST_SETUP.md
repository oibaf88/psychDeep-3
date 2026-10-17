# psychcast — guía de puesta en marcha

Esta guía permite convertir la rama de preparación en un repositorio y despliegue independientes. **No apuntes psychcast a la base de datos de producción de psychDeep.**

## 1. Crear el repositorio nuevo

1. Crea en GitHub un repositorio vacío llamado `psychcast` bajo la cuenta deseada.
2. Clona la rama de preparación del repositorio de origen y publica su contenido en el nuevo repositorio. Ejemplo en PowerShell:

```powershell
git clone --branch feature/psychcast-handoff-2026-10 https://github.com/oibaf88/psychDeep-3.git psychcast
cd psychcast
git remote rename origin upstream
git remote add origin https://github.com/oibaf88/psychcast.git
git push -u origin HEAD:master
```

Si quieres que el historial completo forme parte del repositorio nuevo, este procedimiento lo conserva. No incluyas archivos .env, dumps de datos clínicos, tokens ni claves.

## 2. Render

Usa `render.psychcast.yaml` como plantilla de Blueprint. Antes de sincronizarla, comprueba que el repositorio `https://github.com/oibaf88/psychcast` ya existe y que la rama elegida contiene este archivo. El Blueprint es independiente del `render.yaml` existente: no reemplaza ni modifica los servicios de psychDeep.

Servicios previstos:
- `psychcast-api`: FastAPI/Docker, raíz `backend`, región Frankfurt.
- `psychcast-web`: sitio estático Vite/React, raíz `frontend`.
- Variables sensibles configuradas desde Render Dashboard; nunca en Git.

La creación del servicio y su primer despliegue no deben realizarse contra el repositorio de origen si ello pudiera reutilizar la configuración o los datos de psychDeep. Cuando el repositorio nuevo esté disponible, conecta Render a ese repositorio y revisa el diff de variables antes del primer despliegue.

### Subdominio

Dominio esperado: `psychcast.bfab.io`.

1. En Render, abre el servicio web `psychcast-web` → Settings → Custom Domains y añade `psychcast.bfab.io`.
2. Render mostrará el destino DNS exacto requerido; crea el registro indicado en el proveedor DNS autoritativo de `bfab.io`.
3. Espera a que Render verifique el dominio y emita TLS.
4. Configura la API para aceptar únicamente los orígenes de frontend previstos, incluido `https://psychcast.bfab.io`.
5. No inventes ni reutilices el destino DNS de otro servicio; usa el valor que Render muestre para este servicio.

No se debe declarar el dominio activo hasta que Render confirme la verificación y HTTPS.

## 3. Variables de entorno

El archivo `.env.psychcast.example` enumera nombres y valores de ejemplo no secretos. Rellena los valores reales en Render Dashboard y Supabase. Nunca copies sin revisión las variables de psychDeep: algunas podrían enlazar con la base de datos o los proveedores de producción.

Mínimos a configurar antes de desplegar:
- URL de base de datos de la instancia nueva y esquema objetivo verificado;
- claves públicas/privadas de Supabase según el uso real de la aplicación, con permisos mínimos;
- URL pública de la API y origen del frontend;
- secretos de autenticación, firma y cifrado generados específicamente para psychcast;
- proveedores LLM explícitamente habilitados, modelos permitidos y límites de tiempo/tokens;
- telemetría y auditoría sin registrar texto clínico ni secretos.

No inventar claves. Los marcadores `REPLACE_ME` impiden confundir ejemplos con credenciales funcionales.

## 4. Supabase independiente

Crear un proyecto Supabase nuevo denominado `psychcast` en la organización autorizada. Confirmar el coste del proyecto antes de crear recursos con coste no nulo.

La migración debe ser deliberada y validada:
1. inventariar esquema, tablas, RLS, funciones, triggers, buckets, extensiones, roles, índices y políticas;
2. exportar solo los datos que exista base jurídica y autorización para trasladar;
3. crear primero el esquema en el nuevo proyecto y validar las migraciones en staging;
4. importar datos por lotes con conteos y checksums, manteniendo claves y relaciones cuando proceda;
5. verificar RLS, roles, permisos, fechas, zonas horarias, referencias, consentimientos y auditoría;
6. ejecutar pruebas de lectura/escritura con usuarios de prueba;
7. mantener psychDeep sin cambios y no redirigir tráfico hasta completar pruebas y aprobación explícita.

No copies automáticamente secretos de Auth, claves JWT, URLs de callbacks o credenciales de proveedor. Los usuarios y sesiones pueden requerir un procedimiento de migración específico. La nueva base de datos es la única fuente de verdad para la nueva instancia; no se configura sincronización bidireccional por defecto.

## 5. Verificación previa a producción

- [ ] Repositorio nuevo y rama principal creados.
- [ ] Render apunta al repositorio nuevo, no al de origen.
- [ ] `psychcast-api` no usa DATABASE_URL de psychDeep.
- [ ] `psychcast-web` apunta a la API de psychcast.
- [ ] Dominio personalizado verificado y TLS activo.
- [ ] RLS y autorización probadas con usuarios diferentes.
- [ ] Los cuatro agentes se mantienen y pasan pruebas de contrato.
- [ ] Memoria y predicción tienen permisos, procedencia y auditoría.
- [ ] La predicción está desactivada por defecto.
- [ ] No se han copiado datos personales a logs, GitHub ni servicios no aprobados.
- [ ] Backups y plan de recuperación documentados.
