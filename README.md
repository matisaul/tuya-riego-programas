# Tuya Riego Programas (Home Assistant)

Crea un **switch por cada programa de riego** guardado en la app Tuya / Smart Life
(pantalla *Programs* del controlador de riego) y los mantiene sincronizados:

- Programa nuevo en la app → aparece un switch nuevo en HA.
- Programa borrado en la app → el switch se elimina de HA (también del registro de entidades).
- Programa editado (hora, días, zonas) → el mismo switch actualiza su nombre y atributos.
- Prender/apagar el switch → activa/desactiva el programa en el equipo, igual que el toggle de la app.
  No toca horarios ni duraciones.

Funciona **en local** (LAN, vía `tinytuya`). No usa la nube de Tuya ni consume cuota de API.

## Instalación

1. Copia `custom_components/tuya_riego_programas` a `/config/custom_components/`
   (o en HACS: *Repositorios personalizados* → `https://github.com/matisaul/tuya-riego-programas`, categoría *Integración*).
2. Reinicia Home Assistant.
3. *Ajustes → Dispositivos y servicios → Agregar integración → Tuya Riego Programas*.

### Datos que pide

| Campo | De dónde sale |
|---|---|
| Device ID | Tuya IoT Platform → *Query Devices in Project* (`id`) |
| IP local | Router / DHCP. **No** usar el campo `ip` de Tuya (es la IP pública) |
| Local key | Tuya IoT Platform → *Query Device Details* (`local_key`). Cambia si re-emparejas el equipo |
| Versión de protocolo | Dejar en `auto` (prueba 3.5 → 3.4 → 3.3 → 3.1) |
| DP de programas | `38` (`normal_timer`) |

Conviene fijar la IP del riego en el DHCP del router.

### Opciones

- **Nombres de zona**: por ejemplo zona 1 = "Pasto Terraza". Se usan en el nombre y en los atributos del switch.
- **Intervalo de lectura**: 15 s por defecto. Es el tiempo máximo que tarda HA en ver un cambio hecho en la app.

## Entidades

`switch.<nombre_integración>_programa_<id>`. El `id` lo asigna la app y no cambia al editar el programa,
así que las automatizaciones siguen apuntando al programa correcto.

Atributos: `id_programa`, `hora_inicio`, `dias`, `ciclo`, `modo`, `zonas`, `duracion_total_min`.

## Formato del DP 38 (`normal_timer`)

Base64, 22 bytes por programa, sin cabecera:

| Byte | Contenido |
|---|---|
| 0 | ID del programa |
| 1–2 | Hora de inicio en minutos (big endian) |
| 3 | bits 0–1 activado (01) / desactivado (00) · bits 2–3 secuencial/simultáneo · bits 4–7 semanal/impares/pares |
| 4 | Días (bit0 = domingo … bit6 = sábado; 0 = una vez) |
| 5–9 | Reservado (se conserva sin cambios) |
| 10–21 | Minutos por zona 1–12 (0 = zona sin riego) |

Verificado contra el equipo real con 1 y 2 programas (20:45 todos los días, zona 1 4 min; 06:00 lunes, zona 1 1 min)
y cambiando el toggle en la app.

## Seguridad

- Al cambiar un switch, la integración **lee el valor vigente del equipo**, cambia solo los bits de ese programa
  y escribe el string completo. Si el programa ya no existe, no escribe nada y muestra error.
- Si el equipo no responde, los switches quedan *no disponibles*; **no se borran** por un corte de WiFi.
- Si el valor del DP no calza con el formato (largo no múltiplo de 22, IDs repetidos), no escribe nada.
