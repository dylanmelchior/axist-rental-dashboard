from django.db import models

# Create your models here.

class Customer(models.Model):
    firstName = models.CharField(max_length=100)
    lastName = models.CharField(max_length=100)
    phone = models.BigIntegerField()
    email = models.EmailField()


class OutreachLog(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    lastContacted = models.DateField()
    

