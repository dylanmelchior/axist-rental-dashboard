from django.db import models

# Create your models here.

class Customer(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=200, null = True)
    email = models.EmailField(null = True)
    qb_id = models.BigIntegerField()


class OutreachLog(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    lastContacted = models.DateField()
    

