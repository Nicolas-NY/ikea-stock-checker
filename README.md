# IKEA Mexico Stock Checker 🛒

Monitorea la disponibilidad de productos IKEA México y recibe notificaciones cuando haya stock.

## Productos Monitoreados

| Producto | Artículo | Enlace |
|----------|----------|--------|
| RÅDMANSÖ Mueble de TV (café efecto nogal) | 80598986 | [Ver](https://www.ikea.com/mx/es/p/radmansoe-mueble-de-tv-cafe-efecto-nogal-80598986/) |

> **¿Quieres agregar o quitar productos?** Edita el archivo `products.json` con el número de artículo y nombre de cada producto.

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

Edita `products.json` — puedes tener todos los productos que quieras:

```json
{
  "products": [
    {
      "item_number": "20601053",
      "name": "RÅDMANSÖ Base de cama King",
      "url": "https://www.ikea.com/mx/es/p/radmansoe-base-de-cama-cafe-efecto-nogal-20601053/"
    }
  ]
}
```

El `item_number` sale del final de la URL del producto en ikea.com.

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
├── check_stock.py              # Script principal (multi-producto)
├── products.json               # Lista de productos a monitorear
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
1. Busca el número de artículo en la URL del producto en IKEA (el número al final)
2. Agrégalo al archivo `products.json`
3. Haz commit y push — el workflow se actualiza automáticamente
