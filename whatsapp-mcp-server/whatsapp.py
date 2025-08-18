from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
import os.path
import requests
import json
import audio

WHATSAPP_API_BASE_URL = "http://localhost:8080/api"

@dataclass
class Message:
    timestamp: datetime
    sender: str
    content: str
    is_from_me: bool
    chat_jid: str
    id: str
    chat_name: Optional[str] = None
    media_type: Optional[str] = None

@dataclass
class Chat:
    jid: str
    name: Optional[str]
    last_message_time: Optional[datetime]
    last_message: Optional[str] = None
    last_sender: Optional[str] = None
    last_is_from_me: Optional[bool] = None

    @property
    def is_group(self) -> bool:
        """Determine if chat is a group based on JID pattern."""
        return self.jid.endswith("@g.us")

@dataclass
class Contact:
    phone_number: str
    name: Optional[str]
    jid: str

@dataclass
class MessageContext:
    message: Message
    before: List[Message]
    after: List[Message]

def api_request(endpoint: str, method: str = "GET", params: dict = None, data: dict = None) -> dict:
    """Make an API request to the WhatsApp bridge."""
    url = f"{WHATSAPP_API_BASE_URL}/{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, params=params or {})
        elif method == "POST":
            response = requests.post(url, json=data or {})
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return {}

def list_chats(
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_last_message: bool = True,
    sort_by: str = "last_active"
) -> List[Dict[str, Any]]:
    """Get chats from the WhatsApp bridge API."""
    try:
        chats_data = api_request("chats")
        if not chats_data:
            return []
        
        # Convert to expected format
        result = []
        for chat in chats_data:
            result.append({
                "jid": chat.get("jid", ""),
                "name": chat.get("name", ""),
                "last_message_time": chat.get("last_message_time", ""),
                "is_group": chat.get("is_group", False)
            })
        
        return result
    except Exception as e:
        print(f"Error listing chats: {e}")
        return []

def list_messages(
    after: Optional[str] = None,
    before: Optional[str] = None,
    sender_phone_number: Optional[str] = None,
    chat_jid: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_context: bool = True,
    context_before: int = 1,
    context_after: int = 1
) -> str:
    """Get messages from the WhatsApp bridge API."""
    try:
        params = {"limit": limit}
        if chat_jid:
            params["chat_jid"] = chat_jid
        
        messages_data = api_request("messages", params=params)
        if not messages_data:
            return "No messages found."
        
        # Format messages for display
        output = ""
        for msg in messages_data:
            timestamp_str = msg.get("Time", "")
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    formatted_time = timestamp_str
            else:
                formatted_time = "Unknown time"
            
            sender = msg.get("Sender", "Unknown")
            content = msg.get("Content", "")
            is_from_me = msg.get("IsFromMe", False)
            media_type = msg.get("MediaType", "")
            
            sender_display = "Me" if is_from_me else sender
            
            if media_type:
                output += f"[{formatted_time}] {sender_display}: [{media_type}] {content}\n"
            else:
                output += f"[{formatted_time}] {sender_display}: {content}\n"
        
        return output if output else "No messages to display."
    except Exception as e:
        print(f"Error listing messages: {e}")
        return f"Error retrieving messages: {e}"

def search_contacts(query: str) -> List[Dict[str, Any]]:
    """Search contacts by filtering chats for non-group conversations."""
    try:
        chats = list_chats()
        contacts = []
        
        for chat in chats:
            if not chat.get("is_group", False):  # Only individual chats
                name = chat.get("name", "")
                jid = chat.get("jid", "")
                
                # Simple search in name or JID
                if query.lower() in name.lower() or query.lower() in jid.lower():
                    phone_number = jid.split("@")[0] if "@" in jid else jid
                    contacts.append({
                        "phone_number": phone_number,
                        "name": name,
                        "jid": jid
                    })
        
        return contacts
    except Exception as e:
        print(f"Error searching contacts: {e}")
        return []

def get_chat(chat_jid: str, include_last_message: bool = True) -> Dict[str, Any]:
    """Get chat metadata by JID."""
    try:
        chats = list_chats()
        for chat in chats:
            if chat.get("jid") == chat_jid:
                return chat
        return {}
    except Exception as e:
        print(f"Error getting chat: {e}")
        return {}

def get_direct_chat_by_contact(sender_phone_number: str) -> Dict[str, Any]:
    """Get chat metadata by sender phone number."""
    try:
        chats = list_chats()
        for chat in chats:
            jid = chat.get("jid", "")
            if sender_phone_number in jid and not chat.get("is_group", False):
                return chat
        return {}
    except Exception as e:
        print(f"Error getting direct chat: {e}")
        return {}

def get_contact_chats(jid: str, limit: int = 20, page: int = 0) -> List[Dict[str, Any]]:
    """Get all chats involving the contact."""
    try:
        chats = list_chats()
        result = []
        for chat in chats:
            if jid in chat.get("jid", ""):
                result.append(chat)
        return result[:limit]
    except Exception as e:
        print(f"Error getting contact chats: {e}")
        return []

def get_last_interaction(jid: str) -> str:
    """Get most recent message involving the contact."""
    try:
        # Get messages for this chat
        messages_str = list_messages(chat_jid=jid, limit=1)
        return messages_str if messages_str != "No messages to display." else "No recent interactions found."
    except Exception as e:
        print(f"Error getting last interaction: {e}")
        return f"Error retrieving interaction: {e}"

def get_message_context(
    message_id: str,
    before: int = 5,
    after: int = 5
) -> Dict[str, Any]:
    """Get context around a specific message."""
    # This would require additional API endpoints to implement properly
    return {
        "message": f"Message context for {message_id}",
        "before": [],
        "after": []
    }

def send_message(recipient: str, message: str) -> Tuple[bool, str]:
    """Send a WhatsApp message."""
    try:
        url = f"{WHATSAPP_API_BASE_URL}/send"
        payload = {
            "recipient": recipient,
            "message": message,
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("success", False), result.get("message", "Unknown response")
        else:
            return False, f"Error: HTTP {response.status_code} - {response.text}"
            
    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def send_file(recipient: str, media_path: str) -> Tuple[bool, str]:
    """Send a file via WhatsApp."""
    try:
        if not recipient:
            return False, "Recipient must be provided"
        
        if not media_path:
            return False, "Media path must be provided"
        
        if not os.path.isfile(media_path):
            return False, f"Media file not found: {media_path}"
        
        url = f"{WHATSAPP_API_BASE_URL}/send"
        payload = {
            "recipient": recipient,
            "media_path": media_path
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("success", False), result.get("message", "Unknown response")
        else:
            return False, f"Error: HTTP {response.status_code} - {response.text}"
            
    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def send_audio_message(recipient: str, media_path: str) -> Tuple[bool, str]:
    """Send an audio message via WhatsApp."""
    try:
        if not recipient:
            return False, "Recipient must be provided"
        
        if not media_path:
            return False, "Media path must be provided"
        
        if not os.path.isfile(media_path):
            return False, f"Media file not found: {media_path}"

        if not media_path.endswith(".ogg"):
            try:
                media_path = audio.convert_to_opus_ogg_temp(media_path)
            except Exception as e:
                return False, f"Error converting file to opus ogg. You likely need to install ffmpeg: {str(e)}"
        
        return send_file(recipient, media_path)
        
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def download_media(message_id: str, chat_jid: str) -> Optional[str]:
    """Download media from a message and return the local file path."""
    try:
        url = f"{WHATSAPP_API_BASE_URL}/download"
        payload = {
            "message_id": message_id,
            "chat_jid": chat_jid
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                path = result.get("path")
                print(f"Media downloaded successfully: {path}")
                return path
            else:
                print(f"Download failed: {result.get('message', 'Unknown error')}")
                return None
        else:
            print(f"Error: HTTP {response.status_code} - {response.text}")
            return None
            
    except requests.RequestException as e:
        print(f"Request error: {str(e)}")
        return None
    except json.JSONDecodeError:
        print(f"Error parsing response: {response.text}")
        return None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None