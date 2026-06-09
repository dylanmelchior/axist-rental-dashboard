from django.db import models

# Create your models here.

class Customer(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=200, null = True)
    email = models.EmailField(default = "None", null = True)
    qb_id = models.BigIntegerField()
    sms_consent = models.BooleanField(default = False)

    def __str__(self):
        return self.name


class OutreachLog(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    lastContacted = models.DateTimeField()

class Rental(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    location = models.CharField(max_length = 200)
    totalPrice = models.DecimalField(max_digits = 20, decimal_places = 2, default=0)
    deliveryDate = models.DateTimeField(null = True)
    eventDateStart = models.DateTimeField(null = True)
    eventDateEnd = models.DateTimeField(null = True)
    pickupDate = models.DateTimeField(null = True)

class Item(models.Model):
    name = models.CharField(max_length = 200)
    itemPrice = models.DecimalField(max_digits = 10, decimal_places = 2)
    itemWidth = models.DecimalField(max_digits = 6, decimal_places = 2)
    itemHeight = models.DecimalField(max_digits = 6, decimal_places = 2)
    itemDepth = models.DecimalField(max_digits = 6, decimal_places = 2)
    itemDescription = models.CharField(max_length = 200, null = True)

class RentalItem(models.Model):
    rental = models.ForeignKey(Rental, on_delete = models.CASCADE)
    item = models.ForeignKey(Item, on_delete = models.CASCADE)
    quantity = models.IntegerField()
    notes = models.CharField(max_length = 500, null = True)

class Estimate(models.Model):
    qbID = models.BigIntegerField()
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    location = models.CharField(max_length = 200)
    totalPrice = models.DecimalField(max_digits = 20, decimal_places = 2, default=0)
    deliveryDate = models.DateTimeField(null = True)
    eventDateStart = models.DateTimeField(null = True)
    eventDateEnd = models.DateTimeField(null = True)
    pickupDate = models.DateTimeField(null = True)
    isAccepted = models.BooleanField(default = False)

class EstimateItem(models.Model):
    estimate = models.ForeignKey(Estimate, on_delete = models.CASCADE)
    item = models.ForeignKey(Item, on_delete = models.CASCADE)
    quantity = models.IntegerField()
    notes = models.CharField(max_length = 500, null = True)

class Invoice(models.Model):
    qbID = models.BigIntegerField()
    rental = models.ForeignKey(Rental, on_delete = models.CASCADE)



    

