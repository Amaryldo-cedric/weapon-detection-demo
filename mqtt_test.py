import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    print(f"[{msg.topic}] {msg.payload.decode()}")

# Créer un client MQTT
client = mqtt.Client()

# Se connecter au broker public (gratuit)
client.connect("broker.hivemq.com", 1883, 60)

# S'abonner à un topic
client.subscribe("projet_detection_armes/test")

# Définir ce qui se passe quand on reçoit un message
client.on_message = on_message

# Envoyer un message de test
client.publish("projet_detection_armes/test", "Hello depuis Flask 🎉")

print("✅ Connecté au broker, test en cours... (CTRL+C pour arrêter)")
client.loop_forever()