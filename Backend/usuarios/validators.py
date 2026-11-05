from datetime import datetime, time, timedelta

from django.utils import timezone

from rest_framework.exceptions import ValidationError

from .models import DisponibilidadProveedor, PeriodoNoDisponible

#validators.py
def validar_horario_reserva(proveedor, fecha, hora, duracion_minutos):
    """Valida una reserva contra el horario semanal y los bloqueos del proveedor."""
    if not fecha or not hora:
        return

    hoy = timezone.localdate()
    if fecha < hoy:
        raise ValidationError({
            'fecha_solicitada': 'No se pueden agendar solicitudes para fechas pasadas.'
        })

    if fecha == hoy and hora <= timezone.localtime().time():
        raise ValidationError({
            'hora_solicitada': 'No se pueden agendar horas que ya pasaron o que ya comenzaron.'
        })

    if proveedor and PeriodoNoDisponible.objects.filter(
        proveedor=proveedor,
        fecha_inicio__lte=fecha,
        fecha_fin__gte=fecha,
    ).exists():
        raise ValidationError({
            'fecha_solicitada': 'El proveedor no está disponible en la fecha seleccionada.'
        })

    horarios = (
        DisponibilidadProveedor.objects.filter(proveedor=proveedor)
        if proveedor else DisponibilidadProveedor.objects.none()
    )

    if not horarios.exists():
        # Compatibilidad con proveedores que todavía no han configurado HU-11.
        if fecha.weekday() in (5, 6):
            raise ValidationError({
                'fecha_solicitada': 'El servicio solo atiende de Lunes a Viernes.'
            })

        if not (time(8, 0) <= hora <= time(17, 0)):
            raise ValidationError({
                'hora_solicitada': 'El horario de atención es únicamente de 8:00 AM a 5:00 PM.'
            })
        return

    horario = horarios.filter(dia_semana=fecha.weekday()).first()
    if not horario:
        raise ValidationError({
            'fecha_solicitada': 'El proveedor no atiende el día seleccionado.'
        })

    inicio_solicitud = datetime.combine(fecha, hora)
    fin_solicitud = inicio_solicitud + timedelta(minutes=max(duracion_minutos or 0, 0))
    inicio_atencion = datetime.combine(fecha, horario.hora_inicio)
    fin_atencion = datetime.combine(fecha, horario.hora_fin)
    if inicio_solicitud < inicio_atencion or fin_solicitud > fin_atencion:
        raise ValidationError({
            'hora_solicitada': 'La duración del servicio debe quedar dentro del horario de atención del proveedor.'
        })
