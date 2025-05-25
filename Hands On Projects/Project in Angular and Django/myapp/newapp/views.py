# views.py
from django.http import JsonResponse
from kafka import KafkaProducer
import json

# Kafka Producer Configuration
producer = KafkaProducer(bootstrap_servers='localhost:9092', value_serializer=lambda v: json.dumps(v).encode('utf-8'))

def send_text(request):
    if request.method == 'POST':
        text_data = request.POST.get('text_data')
        
        # Send text data to Kafka
        producer.send('text_topic', {'message': text_data})

        return JsonResponse({'status': 'Message sent', 'data': text_data})

    return JsonResponse({'error': 'Only POST method is allowed'}, status=400)
