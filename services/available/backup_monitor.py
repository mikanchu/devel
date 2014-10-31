#!/usr/bin/python
#backup_monitor.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: backup_monitor

"""

from services.local_service import LocalService

def create_service():
    return BackupMonitorService()
    
class BackupMonitorService(LocalService):
    
    service_name = 'backup_monitor'
    
    def dependent_on(self):
        return ['list_files',
                'fire_hire',
                'rebuilding',
                ]
    
    def start(self):
        return True
    
    def stop(self):
        return True
    
    

    