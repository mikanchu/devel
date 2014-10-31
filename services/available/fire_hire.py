#!/usr/bin/python
#fire_hire.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: fire_hire

"""

from services.local_service import LocalService

def create_service():
    return FireHireService()
    
class FireHireService(LocalService):
    
    service_name = 'fire_hire'
    
    def dependent_on(self):
        return ['customer',
                ]
    
    def start(self):
        from p2p import fire_hire
        fire_hire.A('init')
        return True
    
    def stop(self):
        from p2p import fire_hire
        fire_hire.Destroy()
        return True
    
    

    