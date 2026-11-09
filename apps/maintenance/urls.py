from django.urls import path

from . import execution_views, picker_views, recurrence_views, views

app_name = "maintenance"
urlpatterns = [
    path(
        "ejecuciones/<int:run_id>/avances/",
        execution_views.run_action,
        {"action": "avances"},
        name="group_progress",
    ),
    path(
        "ejecuciones/<int:run_id>/equipos/<int:participant_id>/avances/",
        execution_views.run_action,
        {"action": "avances"},
        name="device_progress",
    ),
    path(
        "ejecuciones/<int:run_id>/equipos/<int:participant_id>/completar/",
        execution_views.run_action,
        {"action": "completar"},
        name="complete_device",
    ),
    path(
        "ejecuciones/<int:run_id>/equipos/<int:participant_id>/omitir/",
        execution_views.run_action,
        {"action": "omitir"},
        name="omit_device",
    ),
    path("ejecuciones/<int:run_id>/<str:action>/", execution_views.run_action, name="run_action"),
    path("", views.maintenance_list, name="list"),
    path("nuevo/", views.maintenance_edit, name="create"),
    path("equipos/selector/", picker_views.device_picker, name="device_picker"),
    path("<int:pk>/equipos/selector/", picker_views.device_picker, name="device_picker_edit"),
    path("<int:pk>/", views.maintenance_detail, name="detail"),
    path("<int:pk>/ejecuciones/", recurrence_views.executions, name="executions"),
    path("<int:pk>/ejecuciones/<int:run_id>/", views.maintenance_detail, name="run_detail"),
    path("<int:pk>/vencimientos/", recurrence_views.due_dates, name="due_dates"),
    path("<int:pk>/siguiente/", recurrence_views.next_run, name="next_run"),
    path("<int:pk>/editar/", views.maintenance_edit, name="edit"),
    path("<int:pk>/historial/", views.maintenance_history, name="history"),
]
