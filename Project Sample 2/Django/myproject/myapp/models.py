from djongo import models
class data(models.Model):
    text_input=models.CharField(max_length=255)
    bool_input=models.BooleanField()
    pdf_input=models.FileField(upload_to='pdf/')
    photo_input=models.ImageField(upload_to='img/')
    csv_input=models.FileField(upload_to='csvs/')
    timestamp=models.DateTimeField(auto_now_add=True)
      