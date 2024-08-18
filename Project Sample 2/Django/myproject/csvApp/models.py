from djongo import models

# Create your models here.
class CSVData(models.Model):
    Name=models.CharField(max_length=300)
    Age=models.IntegerField()
    Degree=models.CharField(max_length=100)
    def __str__(self):
        return self.name