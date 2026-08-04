# IKEA Mexico Stock Checker 🛒

Monitorea la disponibilidad de productos IKEA México y recibe notificaciones cuando haya stock.

## Producto Monitoreado

- **RÅDMANSÖ Base de cama King** (café efecto nogal)
- Artículo: 20601053
- [Ver en IKEA México](https://www.ikea.com/mx/es/p/radmansoe-base-de-cama-cafe-efecto-nogal-20601053/)

## Configuración

### 1. Configurar ntfy.sh (notificaciones)

1. Instala la app **ntfy** en tu celular:
   - iOS: [App Store](https://apps.apple.com/app/ntfy/id1625396347)
   - Android: [Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy)

2. Abre la app y suscríbete a un tópico (ej: `ikea-stock-radman`)

3. En GitHub, ve a **Settings > Secrets and variables > Actions** y crea:
   - `NTFY_TOPIC`: El nombre de tu tópico (ej: `ikea-stock-radman`)
   - `NTFY_TOKEN` (opcional): Si usas un tópico privado, agrega tu token

### 2. GitHub Actions

El workflow está configurado para ejecutarse cada 30 minutos. Para activarlo:

1. Haz push de este repositorio a GitHub
2. Ve a la pestaña **Actions** del repositorio
3. Habilita los workflows si es necesario

### 3. Ejecutar manualmente

Ve a **Actions > IKEA Stock Checker > Run workflow** para verificar manualmente.

## Personalizar

### Cambiar el producto

Edita las variables en `.github/workflows/ikea-stock.yml`:

```yaml
env:
  IKEA_ITEM_NUMBER: 'TU_NUMERO_DE_ARTICULO'
  IKEA_PRODUCT_NAME: 'NOMBRE DEL PRODUCTO'
  IKEA_PRODUCT_URL: 'URL_DEL_PRODUCTO'
```

### Cambiar la frecuencia

Edita el cron en el workflow:

```yaml
schedule:
  - cron: '0 9 * * *'  # Diario a las 9 AM (hora Ciudad de México)
  # - cron: '0 */6 * * *'  # Cada 6 horas
  # - cron: '0 8,12,18 * * *'  # 3 veces al día
  # - cron: '0 9 * * 1-5'  # Solo lunes a viernes
```

## Ejecutar localmente

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
export NTFY_TOPIC="tu-topico"
export IKEA_ITEM_NUMBER="20601053"

# Ejecutar
python check_stock.py
```

## Logs

El script guarda un historial en `stock_log.jsonl` con cada verificación.

## Estructura del Proyecto

```
ikea-stock-checker/
├── check_stock.py              # Script principal
├── requirements.txt            # Dependencias Python
├── .github/
│   └── workflows/
│       └── ikea-stock.yml      # GitHub Actions workflow
├── stock_log.jsonl             # Historial (se crea automáticamente)
└── README.md                   # Este archivo
```

## Solución de Problemas

### No recibo notificaciones
1. Verifica que el tópico en ntfy.sh coincida con `NTFY_TOPIC`
2. Asegúrate de estar suscrito al tópico en la app
3. Revisa los logs de GitHub Actions

### Error en la verificación
- IKEA puede bloquear requests automatizados temporalmente
- El workflow fallará silenciosamente y reintentará en la siguiente ejecución

### Quiero agregar otro producto
1. Busca el número de artículo en la URL del producto en IKEA
2. Actualiza las variables de entorno en el workflow
3. Crea un segundo workflow o modifica el script para múltiples productos
