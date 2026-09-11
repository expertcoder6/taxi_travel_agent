"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Car,
  Bike,
  Navigation,
  Phone,
  MessageSquare,
  Activity,
  CheckCircle2,
  Clock,
  MapPin,
  RefreshCw,
  Send,
  PhoneCall,
  PhoneOff,
  Mic,
  Square,
  Shield,
  Zap,
  Users,
  AlertTriangle,
  RotateCcw,
  Sliders,
  ChevronRight,
  Terminal,
  BellRing,
  Volume2,
} from "lucide-react";

interface Driver {
  id: number;
  name: string;
  phone_number: string;
  vehicle_type: "car" | "bike" | "auto";
  vehicle_number: string;
  current_lat: number;
  current_lng: number;
  availability_status: "available" | "on_trip" | "offline";
  rating: number;
}

interface Ride {
  id: number;
  employee_id: number;
  employee_name: string;
  employee_phone: string;
  driver_id: number | null;
  driver_name: string | null;
  driver_phone: string | null;
  vehicle_number: string | null;
  pickup_address: string;
  destination_address: string;
  vehicle_type: string;
  passenger_count?: number;
  scheduled_time?: string;
  fare_estimate: number;
  status: string;
  channel: string;
  created_at: string;
}

interface MCPLog {
  timestamp: number;
  tool_name: string;
  arguments: any;
  result?: any;
  error?: string;
  latency_ms: number;
  status: string;
}

interface NotificationEvent {
  timestamp: string;
  ride_id: number;
  employee_name: string;
  employee_message: string;
  driver_name: string;
  driver_message: string;
  channels_used: string[];
  delivery_mode: string;
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<"fleet" | "simulator" | "inspector">("fleet");
  const [simChannel, setSimChannel] = useState<"message" | "call">("message");

  // Stats & Data
  const [stats, setStats] = useState<any>(null);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [rides, setRides] = useState<Ride[]>([]);
  const [mcpLogs, setMcpLogs] = useState<MCPLog[]>([]);
  const [notifications, setNotifications] = useState<NotificationEvent[]>([]);
  const [loading, setLoading] = useState(false);

  // Filters
  const [vehicleFilter, setVehicleFilter] = useState<string>("all");
  const [driverStatusFilter, setDriverStatusFilter] = useState<string>("all");
  const [rideStatusFilter, setRideStatusFilter] = useState<string>("all");

  // Message Simulator State
  const [simPhone, setSimPhone] = useState("+14155552671");
  const [simSessionId, setSimSessionId] = useState(`sim_sms_${Date.now()}`);
  const [chatMessages, setChatMessages] = useState<
    Array<{ sender: "user" | "bot"; text: string; time: string; tools?: any[] }>
  >([
    {
      sender: "bot",
      text: "Hello! 👋 I am your AI Ride Booking Assistant. Where would you like to be picked up from today?",
      time: "Just now",
    },
  ]);
  const [messageInput, setMessageInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [currentSlots, setCurrentSlots] = useState<any>({});
  const [currentStage, setCurrentStage] = useState<string>("gathering");
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Voice Simulator State
  const [callState, setCallState] = useState<"idle" | "ringing" | "connected" | "ended">("idle");
  const [callTimer, setCallTimer] = useState(0);
  const [voiceTranscript, setVoiceTranscript] = useState<
    Array<{ speaker: "caller" | "ai"; text: string }>
  >([]);
  const [voiceInput, setVoiceInput] = useState("");
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Microphone & Speech-to-Text State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [interimTranscript, setInterimTranscript] = useState("");
  const recognitionRef = useRef<any>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const transcriptRef = useRef<string>("");
  const isRecordingRef = useRef<boolean>(false);

  // SMS Voice Dictation State
  const [isSmsDictating, setIsSmsDictating] = useState(false);
  const smsRecognitionRef = useRef<any>(null);

  // Browser Geolocation State
  const [locatingUser, setLocatingUser] = useState(false);
  const [gpsDetected, setGpsDetected] = useState<{ lat: number; lng: number; address: string } | null>(null);

  // Live Phone Outbound Call State
  const [outboundPhone, setOutboundPhone] = useState("+919644492671");
  const [outboundStatus, setOutboundStatus] = useState<string | null>(null);
  const [outboundLoading, setOutboundLoading] = useState(false);

  const handleTriggerOutboundCall = async () => {
    if (!outboundPhone.trim() || outboundLoading) return;
    setOutboundLoading(true);
    setOutboundStatus("Initiating call to your phone...");
    try {
      const res = await fetch("/voice/call-user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: outboundPhone.trim() }),
      });
      const data = await res.json();
      if (data.success) {
        setOutboundStatus(`📞 Ringing ${data.to}! Answer your phone to speak with the AI Agent.`);
        setTimeout(() => fetchData(), 3000);
      } else {
        setOutboundStatus(`❌ ${data.error || "Could not place call"}`);
      }
    } catch (err: any) {
      setOutboundStatus(`❌ Network error: ${err.message}`);
    } finally {
      setOutboundLoading(false);
    }
  };

  // Fetch initial data
  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsRes, driversRes, ridesRes, mcpRes, notifRes] = await Promise.all([
        fetch("/api/stats").then((r) => r.json()).catch(() => null),
        fetch("/api/drivers").then((r) => r.json()).catch(() => []),
        fetch("/api/rides").then((r) => r.json()).catch(() => []),
        fetch("/api/mcp/tools").then((r) => r.json()).catch(() => ({ recent_executions: [] })),
        fetch("/api/notifications").then((r) => r.json()).catch(() => []),
      ]);

      if (statsRes) setStats(statsRes);
      if (driversRes) setDrivers(driversRes);
      if (ridesRes) setRides(ridesRes);
      if (mcpRes?.recent_executions) setMcpLogs(mcpRes.recent_executions);
      if (notifRes) setNotifications(notifRes);
    } catch (err) {
      console.error("Error fetching dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000);
    return () => clearInterval(interval);
  }, []);

  // Auto scroll chat
  useEffect(() => {
    chatScrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, voiceTranscript]);

  // Voice Call Timer & Call State lifecycle
  useEffect(() => {
    let timerId: any;
    if (callState === "connected") {
      timerId = setInterval(() => setCallTimer((prev) => prev + 1), 1000);
    } else {
      setCallTimer(0);
      if (isRecordingRef.current) {
        stopRecording(false);
      }
    }
    return () => clearInterval(timerId);
  }, [callState]);

  // Cleanup microphone and audio listeners on component unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
      }
      if (smsRecognitionRef.current) {
        try { smsRecognitionRef.current.stop(); } catch (e) {}
      }
    };
  }, []);

  // Handle Send Message (SMS Simulator)
  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || messageInput;
    if (!text.trim() || chatLoading) return;

    setMessageInput("");
    const userMsgTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    setChatMessages((prev) => [
      ...prev,
      { sender: "user", text, time: userMsgTime },
    ]);
    setChatLoading(true);

    try {
      const res = await fetch("/sms/simulate/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: simSessionId,
          phone_number: simPhone,
          message: text,
        }),
      });

      if (!res.body) {
        const fallbackRes = await fetch("/sms/simulate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: simSessionId,
            phone_number: simPhone,
            message: text,
          }),
        });
        const data = await fallbackRes.json();
        const botTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        setChatMessages((prev) => [
          ...prev,
          { sender: "bot", text: data.reply || "Booking processed.", time: botTime, tools: data.mcp_tools_called },
        ]);
        if (data.slots) setCurrentSlots(data.slots);
        if (data.stage) setCurrentStage(data.stage);
        fetchData();
        return;
      }

      // Live SSE Streaming
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let botReplyText = "";
      const botTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      const collectedTools: any[] = [];

      setChatMessages((prev) => [
        ...prev,
        { sender: "bot", text: "", time: botTime, tools: [] },
      ]);

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));
              if (event.type === "token") {
                botReplyText += event.chunk;
                setChatMessages((prev) => {
                  const updated = [...prev];
                  if (updated.length > 0) {
                    updated[updated.length - 1] = {
                      ...updated[updated.length - 1],
                      text: botReplyText,
                      tools: [...collectedTools],
                    };
                  }
                  return updated;
                });
              } else if (event.type === "slot_update") {
                if (event.slots) setCurrentSlots(event.slots);
                if (event.stage) setCurrentStage(event.stage);
              } else if (event.type === "tool_start") {
                collectedTools.push({ name: event.name, arguments: event.arguments });
                setChatMessages((prev) => {
                  const updated = [...prev];
                  if (updated.length > 0) {
                    updated[updated.length - 1] = {
                      ...updated[updated.length - 1],
                      tools: [...collectedTools],
                    };
                  }
                  return updated;
                });
              } else if (event.type === "done") {
                if (event.reply && !botReplyText) {
                  botReplyText = event.reply;
                  setChatMessages((prev) => {
                    const updated = [...prev];
                    if (updated.length > 0) {
                      updated[updated.length - 1] = {
                        ...updated[updated.length - 1],
                        text: botReplyText,
                        tools: [...collectedTools],
                      };
                    }
                    return updated;
                  });
                }
                if (event.slots) setCurrentSlots(event.slots);
                if (event.stage) setCurrentStage(event.stage);
              }
            } catch (e) {
              console.error("SSE parse error:", e);
            }
          }
        }
      }

      fetchData();
    } catch (err) {
      console.error("Error sending simulate message:", err);
    } finally {
      setChatLoading(false);
    }
  };

  // Reset Chat Session
  const resetChatSession = () => {
    const newSession = `sim_sms_${Date.now()}`;
    setSimSessionId(newSession);
    setCurrentSlots({});
    setCurrentStage("gathering");
    setChatMessages([
      {
        sender: "bot",
        text: "Hello! 👋 I am your AI Ride Booking Assistant. Where would you like to be picked up from today?",
        time: "Just now",
      },
    ]);
  };

  // Stop & Clean up voice recording
  const stopRecording = async (shouldSend: boolean = true) => {
    isRecordingRef.current = false;
    setIsRecording(false);
    setInterimTranscript("");

    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }

    // Stop Web Speech API Recognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      recognitionRef.current = null;
    }

    // Stop MediaRecorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }

    // Release microphone hardware stream tracks so browser mic indicator turns off
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (!shouldSend) {
      audioChunksRef.current = [];
      return;
    }

    // 1. Check if speech recognition captured text
    let textToSend = (transcriptRef.current || voiceInput).trim();

    // 2. If Web Speech was empty/unsupported but we have audio chunks, transcribe via Groq Whisper backend
    if (!textToSend && audioChunksRef.current.length > 0) {
      try {
        const mimeType = mediaRecorderRef.current?.mimeType || "audio/webm";
        const recordedBlob = new Blob(audioChunksRef.current, { type: mimeType });
        if (recordedBlob.size > 2000) {
          setVoiceLoading(true);
          const formData = new FormData();
          formData.append("file", recordedBlob, "speech.webm");

          const res = await fetch("/voice/transcribe", {
            method: "POST",
            body: formData,
          });

          if (res.ok) {
            const data = await res.json();
            if (data.text && data.text.trim()) {
              textToSend = data.text.trim();
            }
          }
        }
      } catch (err) {
        console.warn("Audio upload transcription error:", err);
      } finally {
        setVoiceLoading(false);
      }
    }

    audioChunksRef.current = [];

    if (textToSend) {
      setVoiceInput(textToSend);
      handleVoiceTurn(textToSend);
    } else {
      setRecordingError("No speech detected. Please speak closer to your microphone or type your message.");
      setTimeout(() => setRecordingError(null), 5000);
    }
  };

  // Start microphone listening & speech capture
  const startRecording = async () => {
    setRecordingError(null);
    setInterimTranscript("");
    transcriptRef.current = "";
    audioChunksRef.current = [];

    // Interrupt AI if currently speaking via TTS
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }

    // 1. Request microphone hardware stream
    let stream: MediaStream | null = null;
    try {
      if (typeof navigator !== "undefined" && navigator?.mediaDevices?.getUserMedia) {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaStreamRef.current = stream;
      }
    } catch (err: any) {
      console.warn("Microphone getUserMedia error:", err);
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setRecordingError(
          "Microphone permission blocked. Please allow microphone access in your browser address bar."
        );
        return;
      }
    }

    // 2. Start MediaRecorder as backup for Groq Whisper
    if (stream && typeof MediaRecorder !== "undefined") {
      try {
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : MediaRecorder.isTypeSupported("audio/ogg")
          ? "audio/ogg"
          : "";
        const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;
        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };
        recorder.start(250);
      } catch (e) {
        console.warn("MediaRecorder start error:", e);
      }
    }

    // 3. Start Web Speech API SpeechRecognition
    const SpeechRecognitionClass =
      typeof window !== "undefined"
        ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
        : null;

    if (SpeechRecognitionClass) {
      try {
        const recognition = new SpeechRecognitionClass();
        recognition.continuous = true; // Crucial: prevents early 1-second auto cutoff!
        recognition.interimResults = true;
        recognition.lang = "en-IN";
        recognition.maxAlternatives = 1;

        recognition.onresult = (event: any) => {
          let interim = "";
          let final = transcriptRef.current || "";

          for (let i = event.resultIndex; i < event.results.length; ++i) {
            const piece = event.results[i][0]?.transcript || "";
            if (event.results[i].isFinal) {
              final = (final ? final + " " : "") + piece.trim();
            } else {
              interim += piece;
            }
          }

          transcriptRef.current = final;
          setInterimTranscript(interim);
          const fullText = (final + (interim ? " " + interim : "")).trim();
          if (fullText) {
            setVoiceInput(fullText);
          }

          // Auto-send silence timer: if user speaks and pauses for 3.5s
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = setTimeout(() => {
            if (isRecordingRef.current && (transcriptRef.current || fullText)) {
              stopRecording(true);
            }
          }, 3500);
        };

        recognition.onerror = (event: any) => {
          console.warn("Speech recognition error:", event.error);
          if (event.error === "not-allowed") {
            setRecordingError("Microphone permission blocked. Please allow mic in browser settings.");
          }
        };

        recognition.onend = () => {
          // Keep active if user has not clicked stop
          if (isRecordingRef.current) {
            try {
              recognition.start();
            } catch (e) {}
          }
        };

        recognition.start();
        recognitionRef.current = recognition;
      } catch (e) {
        console.warn("SpeechRecognition init error:", e);
      }
    }

    isRecordingRef.current = true;
    setIsRecording(true);
  };

  // SMS Simulator Voice Dictation
  const toggleSmsDictation = () => {
    const SpeechRecognitionClass =
      typeof window !== "undefined"
        ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
        : null;

    if (!SpeechRecognitionClass) {
      alert("Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.");
      return;
    }

    if (isSmsDictating) {
      if (smsRecognitionRef.current) {
        try { smsRecognitionRef.current.stop(); } catch (e) {}
      }
      setIsSmsDictating(false);
      return;
    }

    try {
      const recognition = new SpeechRecognitionClass();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-IN";

      recognition.onresult = (e: any) => {
        let text = "";
        for (let i = 0; i < e.results.length; ++i) {
          text += e.results[i][0]?.transcript || "";
        }
        if (text) setMessageInput(text);
      };

      recognition.onerror = () => setIsSmsDictating(false);
      recognition.onend = () => setIsSmsDictating(false);

      recognition.start();
      smsRecognitionRef.current = recognition;
      setIsSmsDictating(true);
    } catch (e) {
      console.warn("Could not start SMS dictation:", e);
      setIsSmsDictating(false);
    }
  };

  // Handle Voice Turn
  const handleVoiceTurn = async (spokenText?: string) => {
    if (isRecordingRef.current) {
      stopRecording(false);
    }
    const text = spokenText || voiceInput;
    if (!text.trim() || voiceLoading) return;

    setVoiceInput("");
    setVoiceTranscript((prev) => [...prev, { speaker: "caller", text }]);
    setVoiceLoading(true);

    try {
      const res = await fetch("/voice/simulate/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: `sim_call_${simPhone.replace("+", "")}`,
          phone_number: simPhone,
          user_text: text,
        }),
      });

      if (!res.body) {
        const fallbackRes = await fetch("/voice/simulate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: `sim_call_${simPhone.replace("+", "")}`,
            phone_number: simPhone,
            user_text: text,
          }),
        });
        const data = await fallbackRes.json();
        const aiReply = data.reply || "Thank you. Your request is being handled.";
        setVoiceTranscript((prev) => [...prev, { speaker: "ai", text: aiReply }]);
        if (typeof window !== "undefined" && "speechSynthesis" in window) {
          setIsSpeaking(true);
          const utterance = new SpeechSynthesisUtterance(aiReply);
          utterance.rate = 1.05;
          utterance.onend = () => setIsSpeaking(false);
          utterance.onerror = () => setIsSpeaking(false);
          window.speechSynthesis.speak(utterance);
        }
        return;
      }

      // Stream words into transcript
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let aiReplyText = "";
      setVoiceTranscript((prev) => [...prev, { speaker: "ai", text: "" }]);

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));
              if (event.type === "token") {
                aiReplyText += event.chunk;
                setVoiceTranscript((prev) => {
                  const updated = [...prev];
                  if (updated.length > 0) {
                    updated[updated.length - 1] = {
                      speaker: "ai",
                      text: aiReplyText,
                    };
                  }
                  return updated;
                });
              } else if (event.type === "slot_update") {
                if (event.slots) setCurrentSlots(event.slots);
                if (event.stage) setCurrentStage(event.stage);
              } else if (event.type === "done") {
                if (event.stage === "confirmed" || event.stage === "failed") {
                  setTimeout(() => setCallState("ended"), 6000);
                }
              }
            } catch (e) {
              console.error("SSE parse error:", e);
            }
          }
        }
      }

      // Speak final audio response
      if (aiReplyText && typeof window !== "undefined" && "speechSynthesis" in window) {
        setIsSpeaking(true);
        const utterance = new SpeechSynthesisUtterance(aiReplyText);
        utterance.rate = 1.05;
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);
        window.speechSynthesis.speak(utterance);
      }

      fetchData();
    } catch (err) {
      console.error("Error in voice turn:", err);
    } finally {
      setVoiceLoading(false);
    }
  };

  // Browser Geolocation Handler using HTML5 navigator.geolocation
  const handleUseCurrentLocation = () => {
    if (typeof window === "undefined" || !navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    setLocatingUser(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        try {
          const res = await fetch(`/api/reverse-geocode?lat=${lat}&lng=${lng}`);
          const data = await res.json();
          const addr = data.formatted_address || `GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
          setGpsDetected({ lat, lng, address: addr });

          const promptText = `My current location is ${addr}`;
          if (simChannel === "message") {
            handleSendMessage(promptText);
          } else {
            handleVoiceTurn(promptText);
          }
        } catch (err) {
          const fallback = `My current location is ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
          setGpsDetected({ lat, lng, address: fallback });
          if (simChannel === "message") {
            handleSendMessage(fallback);
          } else {
            handleVoiceTurn(fallback);
          }
        } finally {
          setLocatingUser(false);
        }
      },
      (err) => {
        console.warn("Geolocation permission or hardware warning:", err.message);
        setLocatingUser(false);
        // Realistic fallback for simulated environments or permissions denied
        const fallbackLat = 12.9352;
        const fallbackLng = 77.6245;
        const fallbackAddr = "Koramangala 4th Block, 80 Feet Road, Bangalore";
        setGpsDetected({ lat: fallbackLat, lng: fallbackLng, address: fallbackAddr });
        const promptText = `My current location is ${fallbackAddr}`;
        if (simChannel === "message") {
          handleSendMessage(promptText);
        } else {
          handleVoiceTurn(promptText);
        }
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  };

  // Start Voice Call
  const startCall = () => {
    if (isRecordingRef.current) {
      stopRecording(false);
    }
    setCallState("ringing");
    setVoiceTranscript([]);
    setVoiceInput("");
    setRecordingError(null);
    setInterimTranscript("");
    setTimeout(() => {
      setCallState("connected");
      const greeting = "Welcome to Acme Ride Booking. Where would you like to travel today?";
      setVoiceTranscript([{ speaker: "ai", text: greeting }]);
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        setIsSpeaking(true);
        const utterance = new SpeechSynthesisUtterance(greeting);
        utterance.rate = 1.05;
        utterance.onend = () => setIsSpeaking(false);
        window.speechSynthesis.speak(utterance);
      }
    }, 1200);
  };

  // End Voice Call
  const endCall = () => {
    if (isRecordingRef.current) {
      stopRecording(false);
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
    setCallState("ended");
  };

  // Ride Lifecycle Handlers
  const [smsFeedback, setSmsFeedback] = useState<Record<number, string>>({});
  const [actionLoading, setActionLoading] = useState<Record<number, boolean>>({});

  const handleCompleteRide = async (rideId: number) => {
    try {
      setActionLoading((prev) => ({ ...prev, [rideId]: true }));
      await fetch(`/api/rides/${rideId}/complete`, { method: "POST" });
      fetchData();
    } catch (err) {
      console.error("Error completing ride:", err);
    } finally {
      setActionLoading((prev) => ({ ...prev, [rideId]: false }));
    }
  };

  const handleUpdateRideStatus = async (rideId: number, status: string) => {
    try {
      setActionLoading((prev) => ({ ...prev, [rideId]: true }));
      await fetch(`/api/rides/${rideId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      fetchData();
    } catch (err) {
      console.error("Error updating ride status:", err);
    } finally {
      setActionLoading((prev) => ({ ...prev, [rideId]: false }));
    }
  };

  const handleDriverResponse = async (rideId: number, action: "accept" | "decline") => {
    try {
      setActionLoading((prev) => ({ ...prev, [rideId]: true }));
      await fetch(`/api/rides/${rideId}/driver-response`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      fetchData();
    } catch (err) {
      console.error("Error submitting driver response:", err);
    } finally {
      setActionLoading((prev) => ({ ...prev, [rideId]: false }));
    }
  };

  const handleCancelRide = async (rideId: number) => {
    try {
      setActionLoading((prev) => ({ ...prev, [rideId]: true }));
      await fetch(`/api/rides/${rideId}/cancel`, { method: "POST" });
      fetchData();
    } catch (err) {
      console.error("Error cancelling ride:", err);
    } finally {
      setActionLoading((prev) => ({ ...prev, [rideId]: false }));
    }
  };

  const handleResendSms = async (rideId: number) => {
    try {
      setSmsFeedback((prev) => ({ ...prev, [rideId]: "Sending..." }));
      const res = await fetch(`/api/rides/${rideId}/resend-sms`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        setSmsFeedback((prev) => ({ ...prev, [rideId]: "SMS Sent!" }));
      } else {
        setSmsFeedback((prev) => ({ ...prev, [rideId]: "Failed" }));
      }
      setTimeout(() => {
        setSmsFeedback((prev) => {
          const copy = { ...prev };
          delete copy[rideId];
          return copy;
        });
      }, 3000);
    } catch (err: any) {
      setSmsFeedback((prev) => ({ ...prev, [rideId]: "Error" }));
    }
  };

  // Reset Demo DB
  const handleResetData = async () => {
    try {
      await fetch("/api/reset", { method: "POST" });
      fetchData();
      resetChatSession();
    } catch (err) {
      console.error("Error resetting demo data:", err);
    }
  };

  // Filtered drivers & rides
  const filteredDrivers = drivers.filter((d) => {
    const matchVehicle = vehicleFilter === "all" || d.vehicle_type === vehicleFilter;
    const matchStatus = driverStatusFilter === "all" || d.availability_status === driverStatusFilter;
    return matchVehicle && matchStatus;
  });

  const filteredRides = rides.filter((r) => {
    if (rideStatusFilter === "all") return true;
    if (rideStatusFilter === "pending") return r.status === "pending" || r.status === "booked";
    if (rideStatusFilter === "assigned") return r.status === "confirmed" || r.status === "driver_assigned" || r.status === "driver_accepted";
    if (rideStatusFilter === "ongoing") return r.status === "driver_arriving" || r.status === "ride_started" || r.status === "in_progress";
    if (rideStatusFilter === "completed") return r.status === "completed" || r.status === "ride_completed";
    if (rideStatusFilter === "cancelled") return r.status === "cancelled";
    return r.status === rideStatusFilter;
  });

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div style={{ padding: "24px", maxWidth: "1520px", margin: "0 auto" }}>
      {/* Top Navigation & Status Bar */}
      <header
        className="glass-card"
        style={{
          padding: "16px 20px",
          marginBottom: "20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "14px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "8px",
              background: "#1e293b",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Car size={20} color="#3b82f6" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h1 style={{ fontSize: "1.3rem", fontWeight: "700", color: "#f8fafc" }}>
                Acme Mobility AI
              </h1>
              <span
                style={{
                  background: "rgba(255, 255, 255, 0.06)",
                  color: "#94a3b8",
                  padding: "2px 7px",
                  borderRadius: "4px",
                  fontSize: "0.7rem",
                  fontWeight: "600",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                }}
              >
                MCP PROTOCOL
              </span>
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Autonomous Corporate Transportation • Voice Call & SMS Intake • Live Dispatch
            </p>
          </div>
        </div>

        {/* Live Status & Overview Stats */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px", flexWrap: "wrap" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "7px",
              background: "rgba(34, 197, 94, 0.08)",
              padding: "5px 12px",
              borderRadius: "20px",
              border: "1px solid rgba(34, 197, 94, 0.2)",
            }}
          >
            <div className="live-pulse" />
            <span style={{ fontSize: "0.75rem", color: "#4ade80", fontWeight: "600" }}>
              SYSTEM ONLINE
            </span>
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            <div
              style={{
                background: "#0f172a",
                border: "1px solid var(--border-color)",
                padding: "5px 12px",
                borderRadius: "6px",
                textAlign: "center",
              }}
            >
              <span style={{ fontSize: "0.68rem", color: "var(--text-dim)", display: "block" }}>
                Available Fleet
              </span>
              <strong style={{ fontSize: "0.92rem", color: "#f8fafc" }}>
                {stats?.drivers?.available ?? 0} / {stats?.drivers?.total ?? 0}
              </strong>
            </div>

            <div
              style={{
                background: "#0f172a",
                border: "1px solid var(--border-color)",
                padding: "5px 12px",
                borderRadius: "6px",
                textAlign: "center",
              }}
            >
              <span style={{ fontSize: "0.68rem", color: "var(--text-dim)", display: "block" }}>
                Active Trips
              </span>
              <strong style={{ fontSize: "0.92rem", color: "#f8fafc" }}>
                {stats?.rides?.active ?? 0}
              </strong>
            </div>
          </div>

          <button
            onClick={fetchData}
            className="btn btn-secondary"
            title="Refresh dashboard metrics"
            style={{ padding: "8px 12px" }}
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>

          <button
            onClick={handleResetData}
            className="btn btn-secondary"
            title="Reset database to dummy seed state"
            style={{ padding: "8px 12px", color: "var(--text-muted)" }}
          >
            <RotateCcw size={15} />
            <span style={{ fontSize: "0.8rem" }}>Reset Seed</span>
          </button>
        </div>
      </header>

      {/* LIVE TWILIO INBOUND CALL HOTLINE BANNER */}
      <div
        className="glass-card"
        style={{
          background: "#111827",
          border: "1px solid var(--border-color)",
          borderRadius: "12px",
          padding: "16px 20px",
          marginBottom: "20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "8px",
              background: "#1e293b",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <PhoneCall size={20} color="#3b82f6" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.74rem", color: "var(--text-dim)", fontWeight: "600", letterSpacing: "0.04em" }}>
                LIVE TWILIO HOTLINE:
              </span>
              <a
                href={`tel:${stats?.twilio_phone_number || "+12762089447"}`}
                style={{
                  fontSize: "1.2rem",
                  fontWeight: "700",
                  color: "#f8fafc",
                  letterSpacing: "0.03em",
                  textDecoration: "none",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontFamily: "monospace",
                }}
              >
                {stats?.twilio_phone_number || "+12762089447"}
              </a>
              <span
                style={{
                  background: "rgba(34, 197, 94, 0.08)",
                  color: "#4ade80",
                  border: "1px solid rgba(34, 197, 94, 0.2)",
                  padding: "3px 8px",
                  borderRadius: "12px",
                  fontSize: "0.7rem",
                  fontWeight: "600",
                  display: "flex",
                  alignItems: "center",
                  gap: "5px",
                }}
              >
                <span className="live-pulse" />
                VOICE & SMS READY
              </span>
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "4px", lineHeight: "1.4" }}>
              Call from your phone to talk directly with the AI Voice Agent. State your <strong>pickup</strong>, <strong>destination</strong>, and <strong>vehicle</strong>.
            </p>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "8px", minWidth: "300px", maxWidth: "380px", flex: "1 1 300px" }}>
          {/* Quick Call Phone Widget */}
          <div
            style={{
              background: "#0f172a",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              padding: "10px 14px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
              <span style={{ fontSize: "0.74rem", fontWeight: "600", color: "var(--text-main)", letterSpacing: "0.02em" }}>
                DIRECT CALL TO PHONE
              </span>
              <span style={{ fontSize: "0.68rem", color: "var(--text-dim)" }}>
                Zero Toll
              </span>
            </div>

            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
              <input
                type="text"
                value={outboundPhone}
                onChange={(e) => setOutboundPhone(e.target.value)}
                placeholder="+91..."
                style={{
                  flex: 1,
                  background: "#1e293b",
                  border: "1px solid var(--border-color)",
                  borderRadius: "6px",
                  padding: "6px 10px",
                  fontSize: "0.82rem",
                  color: "#f8fafc",
                  fontFamily: "monospace",
                  outline: "none",
                }}
              />
              <button
                onClick={handleTriggerOutboundCall}
                disabled={outboundLoading || !outboundPhone.trim()}
                className="btn btn-primary"
                style={{
                  padding: "6px 12px",
                  fontSize: "0.78rem",
                  fontWeight: "600",
                  whiteSpace: "nowrap",
                }}
              >
                <PhoneCall size={13} />
                {outboundLoading ? "Calling..." : "Call"}
              </button>
            </div>

            {outboundStatus && (
              <div
                style={{
                  marginTop: "6px",
                  fontSize: "0.74rem",
                  color: outboundStatus.startsWith("❌") ? "#f87171" : "#4ade80",
                  background: "rgba(0,0,0,0.3)",
                  padding: "4px 8px",
                  borderRadius: "4px",
                }}
              >
                {outboundStatus}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Tab Controller */}
      <div
        style={{
          display: "flex",
          gap: "6px",
          marginBottom: "20px",
          background: "#0f172a",
          border: "1px solid var(--border-color)",
          borderRadius: "8px",
          padding: "4px",
          width: "fit-content",
        }}
      >
        <button
          onClick={() => setActiveTab("fleet")}
          className="btn"
          style={{
            background: activeTab === "fleet" ? "var(--primary)" : "transparent",
            color: activeTab === "fleet" ? "#ffffff" : "var(--text-muted)",
            padding: "8px 16px",
            fontSize: "0.8rem",
            border: "none",
          }}
        >
          <Car size={15} />
          Fleet & Dispatch
        </button>

        <button
          onClick={() => setActiveTab("simulator")}
          className="btn"
          style={{
            background: activeTab === "simulator" ? "var(--primary)" : "transparent",
            color: activeTab === "simulator" ? "#ffffff" : "var(--text-muted)",
            padding: "8px 16px",
            fontSize: "0.8rem",
            border: "none",
          }}
        >
          <PhoneCall size={15} />
          Channel Simulator
        </button>

        <button
          onClick={() => setActiveTab("inspector")}
          className="btn"
          style={{
            background: activeTab === "inspector" ? "var(--primary)" : "transparent",
            color: activeTab === "inspector" ? "#ffffff" : "var(--text-muted)",
            padding: "8px 16px",
            fontSize: "0.8rem",
            border: "none",
          }}
        >
          <Terminal size={15} />
          MCP Inspector ({mcpLogs.length})
        </button>
      </div>

      {/* TAB 1: FLEET & RIDES DISPATCH */}
      {activeTab === "fleet" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
          {/* Driver Fleet Grid */}
          <div className="glass-card" style={{ padding: "20px" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
                flexWrap: "wrap",
                gap: "10px",
              }}
            >
              <div>
                <h3 style={{ fontSize: "1.15rem", fontWeight: "600", color: "#f8fafc" }}>
                  Active Driver Fleet ({filteredDrivers.length})
                </h3>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Live location and dispatch availability across vehicle types
                </p>
              </div>

              {/* Vehicle Type Filter */}
              <div style={{ display: "flex", gap: "6px" }}>
                {["all", "car", "bike", "auto"].map((type) => (
                  <button
                    key={type}
                    onClick={() => setVehicleFilter(type)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: "6px",
                      border: "1px solid var(--border-color)",
                      background:
                        vehicleFilter === type ? "rgba(99, 102, 241, 0.3)" : "rgba(255,255,255,0.03)",
                      color: vehicleFilter === type ? "#ffffff" : "var(--text-muted)",
                      fontSize: "0.75rem",
                      cursor: "pointer",
                      textTransform: "capitalize",
                    }}
                  >
                    {type === "all" ? "All" : type === "car" ? "🚗 Car" : type === "bike" ? "🏍️ Bike" : "🛺 Auto"}
                  </button>
                ))}
              </div>
            </div>

            {/* Status Filter */}
            <div style={{ display: "flex", gap: "6px", marginBottom: "16px" }}>
              {["all", "available", "on_trip", "offline"].map((st) => (
                <button
                  key={st}
                  onClick={() => setDriverStatusFilter(st)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "6px",
                    border: "1px solid var(--border-color)",
                    background:
                      driverStatusFilter === st ? "rgba(255,255,255,0.15)" : "transparent",
                    color: driverStatusFilter === st ? "#f8fafc" : "var(--text-dim)",
                    fontSize: "0.72rem",
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                >
                  {st}
                </button>
              ))}
            </div>

            {/* Drivers List */}
            <div style={{ maxHeight: "620px", overflowY: "auto", display: "grid", gap: "10px" }}>
              {filteredDrivers.map((driver) => (
                <div
                  key={driver.id}
                  style={{
                    background: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "10px",
                    padding: "12px 16px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <strong style={{ fontSize: "0.95rem", color: "#f8fafc" }}>
                        {driver.name}
                      </strong>
                      <span
                        style={{
                          background: "rgba(255,255,255,0.06)",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          color: "#38bdf8",
                          fontFamily: "monospace",
                        }}
                      >
                        {driver.vehicle_number}
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "#facc15" }}>
                        ★ {driver.rating}
                      </span>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        marginTop: "4px",
                        fontSize: "0.78rem",
                        color: "var(--text-muted)",
                      }}
                    >
                      <span>📞 {driver.phone_number}</span>
                      <span>
                        Type: <strong style={{ textTransform: "capitalize", color: "#e2e8f0" }}>{driver.vehicle_type}</strong>
                      </span>
                      <span>
                        Coords: {driver.current_lat.toFixed(3)}, {driver.current_lng.toFixed(3)}
                      </span>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span className={`badge badge-${driver.availability_status}`}>
                      {driver.availability_status.replace("_", " ")}
                    </span>
                    {driver.availability_status === "available" && (
                      <button
                        onClick={() => {
                          setActiveTab("simulator");
                          const prompt = `Book with driver ${driver.name} from Acme Tech Park to Koramangala`;
                          if (simChannel === "message") {
                            handleSendMessage(prompt);
                          } else {
                            handleVoiceTurn(prompt);
                          }
                        }}
                        style={{
                          background: "#2563eb",
                          border: "1px solid rgba(255, 255, 255, 0.12)",
                          borderRadius: "6px",
                          padding: "4px 9px",
                          color: "#ffffff",
                          fontSize: "0.72rem",
                          fontWeight: "500",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                          whiteSpace: "nowrap",
                        }}
                        title={`Book a ride directly requesting ${driver.name}`}
                      >
                        Book Driver
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Active Rides Board */}
          <div className="glass-card" style={{ padding: "20px" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
              }}
            >
              <div>
                <h3 style={{ fontSize: "1.15rem", fontWeight: "600", color: "#f8fafc" }}>
                  Live Ride Dispatch Board ({filteredRides.length})
                </h3>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Real-time status transitions from intake to driver assignment
                </p>
              </div>

              {/* Ride Filter Tabs */}
              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                {[
                  { id: "all", label: "All" },
                  { id: "pending", label: "Booked" },
                  { id: "assigned", label: "Assigned" },
                  { id: "ongoing", label: "In Trip" },
                  { id: "completed", label: "Completed" },
                  { id: "cancelled", label: "Cancelled" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setRideStatusFilter(tab.id)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: "6px",
                      border: "1px solid var(--border-color)",
                      background: rideStatusFilter === tab.id ? "rgba(99, 102, 241, 0.35)" : "transparent",
                      color: rideStatusFilter === tab.id ? "#f8fafc" : "var(--text-dim)",
                      fontSize: "0.74rem",
                      fontWeight: rideStatusFilter === tab.id ? "700" : "500",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Rides List */}
            <div style={{ maxHeight: "680px", overflowY: "auto", display: "grid", gap: "14px" }}>
              {filteredRides.length === 0 ? (
                <div
                  style={{
                    padding: "40px 20px",
                    textAlign: "center",
                    color: "var(--text-dim)",
                    fontSize: "0.9rem",
                  }}
                >
                  No rides recorded matching this filter. Switch to the Multi-Channel Simulator or call from your phone to book a ride!
                </div>
              ) : (
                filteredRides.map((ride) => {
                  // Lifecycle step index: 1: booked, 2: assigned, 3: accepted, 4: arriving, 5: started, 6: completed
                  let stepIndex = 1;
                  if (ride.status === "driver_assigned" || ride.status === "confirmed") stepIndex = 2;
                  else if (ride.status === "driver_accepted") stepIndex = 3;
                  else if (ride.status === "driver_arriving") stepIndex = 4;
                  else if (ride.status === "ride_started" || ride.status === "in_progress") stepIndex = 5;
                  else if (ride.status === "ride_completed" || ride.status === "completed") stepIndex = 6;
                  else if (ride.status === "cancelled") stepIndex = 0;

                  const isTerminated = ride.status === "completed" || ride.status === "ride_completed" || ride.status === "cancelled";

                  return (
                    <div
                      key={ride.id}
                      style={{
                        background: "rgba(255, 255, 255, 0.025)",
                        border: "1px solid var(--border-color)",
                        borderRadius: "12px",
                        padding: "16px",
                        transition: "all 0.2s ease",
                      }}
                    >
                      {/* Header Row */}
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          marginBottom: "12px",
                          flexWrap: "wrap",
                          gap: "8px",
                        }}
                      >
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                            <strong style={{ fontSize: "1.05rem", color: "#f8fafc" }}>
                              Booking #{ride.id}
                            </strong>
                            <span
                              style={{
                                background: ride.channel === "call" ? "rgba(236, 72, 153, 0.15)" : "rgba(56, 189, 248, 0.15)",
                                color: ride.channel === "call" ? "#f472b6" : "#38bdf8",
                                padding: "2px 8px",
                                borderRadius: "4px",
                                fontSize: "0.72rem",
                                fontWeight: "600",
                                textTransform: "uppercase",
                              }}
                            >
                              {ride.channel === "call" ? "📞 Voice Call" : "💬 SMS Text"}
                            </span>
                            <span
                              style={{
                                background: "rgba(255, 255, 255, 0.05)",
                                color: "#cbd5e1",
                                padding: "2px 8px",
                                borderRadius: "4px",
                                fontSize: "0.72rem",
                              }}
                            >
                              👥 {ride.passenger_count || 1} Pax
                            </span>
                            <span
                              style={{
                                background: "rgba(255, 255, 255, 0.05)",
                                color: "#cbd5e1",
                                padding: "2px 8px",
                                borderRadius: "4px",
                                fontSize: "0.72rem",
                              }}
                            >
                              🕒 {ride.scheduled_time || "Immediate"}
                            </span>
                            <span className={`badge badge-${ride.status}`}>
                              {ride.status.replace(/_/g, " ")}
                            </span>
                          </div>
                          <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginTop: "4px" }}>
                            Customer: <strong>{ride.employee_name}</strong> ({ride.employee_phone || "Phone caller"})
                          </p>
                        </div>

                        <div style={{ textAlign: "right" }}>
                          <span style={{ fontSize: "1.15rem", fontWeight: "700", color: "#34d399" }}>
                            {ride.fare_estimate ? `₹${ride.fare_estimate}` : "Calculating..."}
                          </span>
                          <span
                            style={{
                              display: "block",
                              fontSize: "0.72rem",
                              color: "var(--text-dim)",
                              textTransform: "uppercase",
                              letterSpacing: "0.05em",
                            }}
                          >
                            {ride.vehicle_type}
                          </span>
                        </div>
                      </div>

                      {/* Real-time Lifecycle Stepper */}
                      {ride.status !== "cancelled" ? (
                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(6, 1fr)",
                            gap: "4px",
                            background: "rgba(0, 0, 0, 0.35)",
                            borderRadius: "8px",
                            padding: "6px 8px",
                            marginBottom: "12px",
                            fontSize: "0.68rem",
                            textAlign: "center",
                          }}
                        >
                          {[
                            { name: "1. Booked", step: 1 },
                            { name: "2. Assigned", step: 2 },
                            { name: "3. Accepted", step: 3 },
                            { name: "4. Arriving", step: 4 },
                            { name: "5. Started", step: 5 },
                            { name: "6. Completed", step: 6 },
                          ].map((s) => {
                            const isCurrent = stepIndex === s.step;
                            const isPast = stepIndex > s.step;
                            return (
                              <div
                                key={s.step}
                                style={{
                                  padding: "4px 2px",
                                  borderRadius: "4px",
                                  background: isCurrent
                                    ? "linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(59, 130, 246, 0.4))"
                                    : isPast
                                    ? "rgba(16, 185, 129, 0.15)"
                                    : "transparent",
                                  color: isCurrent ? "#38bdf8" : isPast ? "#34d399" : "var(--text-dim)",
                                  fontWeight: isCurrent || isPast ? "700" : "500",
                                  border: isCurrent ? "1px solid rgba(56, 189, 248, 0.5)" : "none",
                                }}
                              >
                                {isPast ? "✓ " : ""}{s.name}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div
                          style={{
                            background: "rgba(239, 68, 68, 0.15)",
                            color: "#f87171",
                            padding: "6px 12px",
                            borderRadius: "6px",
                            fontSize: "0.75rem",
                            fontWeight: "600",
                            marginBottom: "12px",
                          }}
                        >
                          ✕ Ride Cancelled
                        </div>
                      )}

                      {/* Locations Card */}
                      <div
                        style={{
                          background: "rgba(0,0,0,0.22)",
                          padding: "10px 14px",
                          borderRadius: "8px",
                          fontSize: "0.82rem",
                          display: "grid",
                          gap: "6px",
                          marginBottom: "12px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ color: "#38bdf8", fontWeight: "600" }}>📍 Pickup:</span>
                          <span style={{ color: "#e2e8f0" }}>{ride.pickup_address || "Pending location"}</span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ color: "#a855f7", fontWeight: "600" }}>🏁 Destination:</span>
                          <span style={{ color: "#e2e8f0" }}>{ride.destination_address || "Pending location"}</span>
                        </div>
                      </div>

                      {/* Driver & Action Toolbar */}
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          fontSize: "0.8rem",
                          flexWrap: "wrap",
                          gap: "10px",
                          paddingTop: "6px",
                          borderTop: "1px solid rgba(255,255,255,0.05)",
                        }}
                      >
                        <div style={{ color: "var(--text-muted)" }}>
                          {ride.driver_name ? (
                            <span>
                              Driver: <strong style={{ color: "#f8fafc" }}>{ride.driver_name}</strong> (
                              {ride.driver_phone || "Contact via App"}) • Vehicle: <code style={{ color: "#38bdf8" }}>{ride.vehicle_number}</code>
                            </span>
                          ) : (
                            <span style={{ color: "#fbbf24" }}>⏳ Matching nearest available driver...</span>
                          )}
                        </div>

                        {/* Interactive Lifecycle Buttons */}
                        <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" }}>
                          {/* Driver Accept / Decline when Assigned */}
                          {(ride.status === "confirmed" || ride.status === "driver_assigned") && (
                            <>
                              <button
                                onClick={() => handleDriverResponse(ride.id, "accept")}
                                disabled={actionLoading[ride.id]}
                                style={{
                                  background: "linear-gradient(135deg, #10b981, #059669)",
                                  border: "none",
                                  borderRadius: "6px",
                                  padding: "5px 10px",
                                  color: "#ffffff",
                                  fontSize: "0.75rem",
                                  fontWeight: "700",
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <CheckCircle2 size={13} />
                                Driver Accept
                              </button>
                              <button
                                onClick={() => handleDriverResponse(ride.id, "decline")}
                                disabled={actionLoading[ride.id]}
                                style={{
                                  background: "rgba(239, 68, 68, 0.2)",
                                  border: "1px solid rgba(239, 68, 68, 0.4)",
                                  borderRadius: "6px",
                                  padding: "5px 10px",
                                  color: "#f87171",
                                  fontSize: "0.75rem",
                                  fontWeight: "600",
                                  cursor: "pointer",
                                }}
                              >
                                Decline (Reassign)
                              </button>
                            </>
                          )}

                          {/* Driver Arriving */}
                          {ride.status === "driver_accepted" && (
                            <button
                              onClick={() => handleUpdateRideStatus(ride.id, "driver_arriving")}
                              disabled={actionLoading[ride.id]}
                              style={{
                                background: "linear-gradient(135deg, #3b82f6, #1d4ed8)",
                                border: "none",
                                borderRadius: "6px",
                                padding: "5px 10px",
                                color: "#ffffff",
                                fontSize: "0.75rem",
                                fontWeight: "700",
                                cursor: "pointer",
                              }}
                            >
                              🚗 Mark Arriving
                            </button>
                          )}

                          {/* Start Trip */}
                          {ride.status === "driver_arriving" && (
                            <button
                              onClick={() => handleUpdateRideStatus(ride.id, "ride_started")}
                              disabled={actionLoading[ride.id]}
                              style={{
                                background: "linear-gradient(135deg, #8b5cf6, #6d28d9)",
                                border: "none",
                                borderRadius: "6px",
                                padding: "5px 10px",
                                color: "#ffffff",
                                fontSize: "0.75rem",
                                fontWeight: "700",
                                cursor: "pointer",
                              }}
                            >
                              ▶ Start Trip
                            </button>
                          )}

                          {/* Complete Trip */}
                          {(ride.status === "ride_started" || ride.status === "in_progress") && (
                            <button
                              onClick={() => handleCompleteRide(ride.id)}
                              disabled={actionLoading[ride.id]}
                              className="btn btn-success"
                              style={{ padding: "5px 10px", fontSize: "0.75rem", fontWeight: "700" }}
                            >
                              <CheckCircle2 size={13} />
                              Complete Trip
                            </button>
                          )}

                          {/* Resend Customer Confirmation SMS */}
                          <button
                            onClick={() => handleResendSms(ride.id)}
                            style={{
                              background: "rgba(255, 255, 255, 0.06)",
                              border: "1px solid var(--border-color)",
                              borderRadius: "6px",
                              padding: "5px 10px",
                              color: smsFeedback[ride.id] ? "#34d399" : "var(--text-dim)",
                              fontSize: "0.74rem",
                              cursor: "pointer",
                            }}
                          >
                            {smsFeedback[ride.id] || "✉ Resend SMS"}
                          </button>

                          {/* Cancel button */}
                          {!isTerminated && (
                            <button
                              onClick={() => handleCancelRide(ride.id)}
                              disabled={actionLoading[ride.id]}
                              style={{
                                background: "transparent",
                                border: "1px solid rgba(239, 68, 68, 0.3)",
                                borderRadius: "6px",
                                padding: "5px 8px",
                                color: "#f87171",
                                fontSize: "0.74rem",
                                cursor: "pointer",
                              }}
                            >
                              Cancel
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: INTERACTIVE CHANNEL SIMULATOR */}
      {activeTab === "simulator" && (
        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "24px" }}>
          {/* Simulator Settings & Persona Panel */}
          <div className="glass-card" style={{ padding: "20px" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: "600", marginBottom: "12px", color: "#f8fafc" }}>
              Simulation Profile
            </h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "16px" }}>
              Test the conversational slot-filling pipeline as an authorized employee.
            </p>

            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-dim)", marginBottom: "6px" }}>
                Select Employee Identity:
              </label>
              <select
                value={simPhone}
                onChange={(e) => setSimPhone(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--bg-input)",
                  border: "1px solid var(--border-color)",
                  color: "#f8fafc",
                  borderRadius: "8px",
                  outline: "none",
                  fontSize: "0.85rem",
                }}
              >
                <option value="+14155552671">Sarah Connor (+14155552671)</option>
                <option value="+919876543210">Priya Raman (+919876543210)</option>
                <option value="+14155553892">Alex Mercer (+14155553892)</option>
                <option value="+919888877777">Aarav Mehta (+919888877777)</option>
                <option value="+1234567890">Demo Tester (+1234567890)</option>
              </select>
            </div>

            {/* Channel Switcher */}
            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-dim)", marginBottom: "6px" }}>
                Active Channel:
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                <button
                  onClick={() => setSimChannel("message")}
                  className={`btn ${simChannel === "message" ? "btn-primary" : "btn-secondary"}`}
                  style={{ padding: "8px" }}
                >
                  <MessageSquare size={16} />
                  SMS / Text
                </button>
                <button
                  onClick={() => setSimChannel("call")}
                  className={`btn ${simChannel === "call" ? "btn-primary" : "btn-secondary"}`}
                  style={{ padding: "8px" }}
                >
                  <Phone size={16} />
                  Voice Call
                </button>
              </div>
            </div>

            {/* Live Slot Status Box */}
            <div
              style={{
                background: "rgba(0,0,0,0.3)",
                padding: "14px",
                borderRadius: "10px",
                border: "1px solid var(--border-color)",
                marginBottom: "20px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", textTransform: "uppercase" }}>
                  Live Slot Status
                </span>
                <span className={`badge badge-${currentStage}`}>{currentStage}</span>
              </div>

              <div style={{ display: "grid", gap: "6px", fontSize: "0.8rem" }}>
                <div>
                  <span style={{ color: "var(--text-dim)" }}>Pickup: </span>
                  <strong style={{ color: currentSlots.pickup ? "#f8fafc" : "#64748b" }}>
                    {currentSlots.pickup || "Pending"}
                  </strong>
                </div>
                <div>
                  <span style={{ color: "var(--text-dim)" }}>Destination: </span>
                  <strong style={{ color: currentSlots.destination ? "#f8fafc" : "#64748b" }}>
                    {currentSlots.destination || "Pending"}
                  </strong>
                </div>
                <div>
                  <span style={{ color: "var(--text-dim)" }}>Vehicle: </span>
                  <strong style={{ color: currentSlots.vehicle_type ? "#f8fafc" : "#64748b", textTransform: "capitalize" }}>
                    {currentSlots.vehicle_type || "Pending"}
                  </strong>
                </div>
                <div>
                  <span style={{ color: "var(--text-dim)" }}>Driver: </span>
                  <strong style={{ color: currentSlots.requested_driver ? "#60a5fa" : "#64748b" }}>
                    {currentSlots.requested_driver || "Nearest Available"}
                  </strong>
                </div>

                {/* Geolocation Button in Sidebar */}
                <button
                  onClick={handleUseCurrentLocation}
                  disabled={locatingUser}
                  style={{
                    marginTop: "8px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "6px",
                    width: "100%",
                    padding: "7px 10px",
                    background: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "6px",
                    color: "#e2e8f0",
                    fontSize: "0.78rem",
                    fontWeight: "500",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                  title="Detect GPS coordinates and set pickup automatically"
                >
                  <Navigation size={13} style={{ animation: locatingUser ? "spin 1s linear infinite" : "none" }} />
                  {locatingUser ? "Acquiring GPS Location..." : "📍 Use My Current Location"}
                </button>
              </div>
            </div>

            {/* Quick Test Prompt Shortcuts */}
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", display: "block", marginBottom: "8px" }}>
                Quick Test Prompts:
              </span>
              <div style={{ display: "grid", gap: "6px" }}>
                {[
                  "Book with driver Rajesh Kumar from Acme Tech Park to Koramangala",
                  "Need a car with driver Suresh to Indiranagar",
                  "Pickup at Acme Tech Park, where i have to reach is Koramangala",
                  "Need a car from Acme Tech Park to Koramangala",
                  "Where i have to reach is Whitefield by bike",
                  "I want an auto from Acme Tech Park to Kempegowda Airport",
                  "Drop me at Koramangala",
                  "I want a ride from Nowhere on Mars to office",
                ].map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      if (simChannel === "message") {
                        handleSendMessage(prompt);
                      } else {
                        handleVoiceTurn(prompt);
                      }
                    }}
                    style={{
                      textAlign: "left",
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid var(--border-color)",
                      color: "var(--text-muted)",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      fontSize: "0.75rem",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--primary)";
                      e.currentTarget.style.color = "#f8fafc";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--border-color)";
                      e.currentTarget.style.color = "var(--text-muted)";
                    }}
                  >
                    "{prompt}"
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={resetChatSession}
              className="btn btn-secondary"
              style={{ width: "100%", marginTop: "18px", fontSize: "0.8rem" }}
            >
              <RotateCcw size={14} />
              Reset Conversation Session
            </button>
          </div>

          {/* Channel Conversation View */}
          <div className="glass-card" style={{ padding: "20px", display: "flex", flexDirection: "column", height: "700px" }}>
            {simChannel === "message" ? (
              /* SMS CHAT INTERFACE */
              <>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderBottom: "1px solid var(--border-color)",
                    paddingBottom: "12px",
                    marginBottom: "16px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <MessageSquare size={20} color="#38bdf8" />
                    <div>
                      <h4 style={{ fontSize: "1rem", color: "#f8fafc" }}>SMS / WhatsApp Channel</h4>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                        Session ID: {simSessionId}
                      </span>
                    </div>
                  </div>

                  <span className={`badge badge-${currentStage}`}>{currentStage}</span>
                </div>

                {/* Message Thread */}
                <div
                  style={{
                    flex: 1,
                    overflowY: "auto",
                    display: "flex",
                    flexDirection: "column",
                    gap: "14px",
                    paddingRight: "8px",
                  }}
                >
                  {chatMessages.map((msg, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: msg.sender === "user" ? "flex-end" : "flex-start",
                      }}
                    >
                      <div
                        style={{
                          maxWidth: "75%",
                          padding: "10px 14px",
                          borderRadius:
                            msg.sender === "user"
                              ? "12px 12px 2px 12px"
                              : "12px 12px 12px 2px",
                          background:
                            msg.sender === "user"
                              ? "#2563eb"
                              : "#1e293b",
                          border:
                            msg.sender === "user"
                              ? "none"
                              : "1px solid var(--border-color)",
                          color: "#f8fafc",
                          fontSize: "0.88rem",
                          whiteSpace: "pre-line",
                          lineHeight: "1.45",
                        }}
                      >
                        {msg.text}
                      </div>

                      {/* Tool Calls Summary Badge */}
                      {msg.tools && msg.tools.length > 0 && (
                        <div
                          style={{
                            marginTop: "6px",
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "6px",
                          }}
                        >
                          {msg.tools.map((t: any, tidx: number) => (
                            <span
                              key={tidx}
                              style={{
                                background: "rgba(168, 85, 247, 0.15)",
                                color: "#c084fc",
                                border: "1px solid rgba(168, 85, 247, 0.3)",
                                padding: "2px 8px",
                                borderRadius: "4px",
                                fontSize: "0.7rem",
                                fontFamily: "monospace",
                              }}
                            >
                              ⚡ MCP: {t.name}
                            </span>
                          ))}
                        </div>
                      )}

                      <span style={{ fontSize: "0.7rem", color: "var(--text-dim)", marginTop: "4px" }}>
                        {msg.time}
                      </span>
                    </div>
                  ))}
                  {chatLoading && (
                    <div style={{ alignSelf: "flex-start", color: "var(--text-dim)", fontSize: "0.85rem" }}>
                      AI Agent thinking & evaluating MCP tools...
                    </div>
                  )}
                  <div ref={chatScrollRef} />
                </div>

                {/* Input Bar */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendMessage();
                  }}
                  style={{
                    display: "flex",
                    gap: "10px",
                    marginTop: "16px",
                    paddingTop: "14px",
                    borderTop: "1px solid var(--border-color)",
                  }}
                >
                  <input
                    type="text"
                    value={messageInput}
                    onChange={(e) => setMessageInput(e.target.value)}
                    placeholder="Type ride request (e.g. 'From Acme Tech Park to Whitefield by car')..."
                    style={{
                      flex: 1,
                      padding: "12px 16px",
                      background: "var(--bg-input)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "8px",
                      color: "#f8fafc",
                      fontSize: "0.9rem",
                      outline: "none",
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleUseCurrentLocation}
                    disabled={locatingUser || chatLoading}
                    className="btn btn-secondary"
                    title="Detect and use my device GPS location"
                    style={{
                      padding: "0 14px",
                      background: "rgba(56, 189, 248, 0.12)",
                      border: "1px solid rgba(56, 189, 248, 0.35)",
                      color: "#38bdf8",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      fontSize: "0.85rem",
                      whiteSpace: "nowrap",
                    }}
                  >
                    <Navigation size={15} style={{ animation: locatingUser ? "spin 1s linear infinite" : "none" }} />
                    {locatingUser ? "Locating..." : "📍 GPS"}
                  </button>
                  <button
                    type="button"
                    onClick={toggleSmsDictation}
                    className={`btn ${isSmsDictating ? "btn-recording" : "btn-secondary"}`}
                    title={isSmsDictating ? "Listening... click to stop dictating" : "Dictate message using microphone"}
                    style={{
                      padding: "0 12px",
                      color: isSmsDictating ? "#ffffff" : "#94a3b8",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      fontSize: "0.85rem",
                      whiteSpace: "nowrap",
                    }}
                  >
                    <Mic size={15} />
                    {isSmsDictating ? "Listening..." : "Mic"}
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={chatLoading}>
                    <Send size={16} />
                    Send
                  </button>
                </form>
              </>
            ) : (
              /* VOICE CALL INTERFACE */
              <>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderBottom: "1px solid var(--border-color)",
                    paddingBottom: "12px",
                    marginBottom: "16px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <Phone size={20} color="#f472b6" />
                    <div>
                      <h4 style={{ fontSize: "1rem", color: "#f8fafc" }}>Voice Call Simulation</h4>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                        Public Inbound Line: +1 (800) ACME-RIDE • STT: Groq Whisper
                      </span>
                    </div>
                  </div>

                  <span
                    style={{
                      background:
                        callState === "connected"
                          ? "rgba(16, 185, 129, 0.2)"
                          : callState === "ringing"
                          ? "rgba(245, 158, 11, 0.2)"
                          : "rgba(255,255,255,0.05)",
                      color:
                        callState === "connected"
                          ? "#34d399"
                          : callState === "ringing"
                          ? "#fbbf24"
                          : "var(--text-dim)",
                      padding: "4px 12px",
                      borderRadius: "20px",
                      fontSize: "0.8rem",
                      fontWeight: "600",
                    }}
                  >
                    {callState === "connected"
                      ? `CONNECTED (${formatSeconds(callTimer)})`
                      : callState.toUpperCase()}
                  </span>
                </div>

                {/* Call Status Visualizer */}
                {callState === "idle" || callState === "ended" ? (
                  <div
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "16px",
                    }}
                  >
                    <div
                      style={{
                        width: "80px",
                        height: "80px",
                        borderRadius: "50%",
                        background: "rgba(99, 102, 241, 0.15)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        border: "1px solid rgba(99, 102, 241, 0.3)",
                      }}
                    >
                      <PhoneCall size={36} color="#818cf8" />
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <h3 style={{ fontSize: "1.2rem", color: "#f8fafc" }}>
                        Call Acme Ride Dispatch
                      </h3>
                      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "4px" }}>
                        Experience the Speech-to-Text → LLM Agent → Text-to-Speech voice pipeline.
                      </p>
                    </div>

                    <button
                      onClick={startCall}
                      className="btn btn-primary"
                      style={{ padding: "12px 28px", fontSize: "1rem" }}
                    >
                      <PhoneCall size={18} />
                      Start Voice Call
                    </button>
                  </div>
                ) : (
                  <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                    {/* Dynamic Call Audio & Microphone Status Indicator */}
                    <div
                      style={{
                        background: isRecording
                          ? "rgba(220, 38, 38, 0.12)"
                          : isSpeaking
                          ? "rgba(16, 185, 129, 0.1)"
                          : "rgba(0,0,0,0.3)",
                        border: isRecording
                          ? "1px solid rgba(239, 68, 68, 0.35)"
                          : isSpeaking
                          ? "1px solid rgba(16, 185, 129, 0.25)"
                          : "1px solid var(--border-color)",
                        padding: "10px 16px",
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "14px",
                        transition: "all 0.2s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        {isRecording ? (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <div
                              style={{
                                width: "10px",
                                height: "10px",
                                borderRadius: "50%",
                                background: "#ef4444",
                                animation: "recording-pulse 1.2s infinite ease-out",
                              }}
                            />
                            <Mic size={18} color="#f87171" />
                            <span style={{ fontSize: "0.85rem", color: "#fca5a5", fontWeight: "600" }}>
                              Microphone Active • Listening to your voice... Speak now!
                            </span>
                          </div>
                        ) : isSpeaking ? (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <Volume2 size={18} color="#34d399" />
                            <span style={{ fontSize: "0.85rem", color: "#34d399", fontWeight: "500" }}>
                              AI Agent Speaking (TTS active)... Click Speak to interrupt.
                            </span>
                          </div>
                        ) : voiceLoading ? (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <RefreshCw size={16} color="#fbbf24" style={{ animation: "spin 1s linear infinite" }} />
                            <span style={{ fontSize: "0.85rem", color: "#fbbf24" }}>
                              Transcribing audio & orchestrating dispatch MCP tools...
                            </span>
                          </div>
                        ) : (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <Mic size={17} color="#94a3b8" />
                            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                              Microphone Ready • Click <strong>Speak</strong> to talk or type your reply below.
                            </span>
                          </div>
                        )}
                      </div>

                      <div style={{ display: "flex", gap: "4px", alignItems: "center", height: "26px" }}>
                        <div className={isRecording ? "wave-bar wave-bar-recording" : "wave-bar"} style={{ opacity: isSpeaking || isRecording ? 1 : 0.25 }} />
                        <div className={isRecording ? "wave-bar wave-bar-recording" : "wave-bar"} style={{ opacity: isSpeaking || isRecording ? 1 : 0.25 }} />
                        <div className={isRecording ? "wave-bar wave-bar-recording" : "wave-bar"} style={{ opacity: isSpeaking || isRecording ? 1 : 0.25 }} />
                        <div className={isRecording ? "wave-bar wave-bar-recording" : "wave-bar"} style={{ opacity: isSpeaking || isRecording ? 1 : 0.25 }} />
                        <div className={isRecording ? "wave-bar wave-bar-recording" : "wave-bar"} style={{ opacity: isSpeaking || isRecording ? 1 : 0.25 }} />
                      </div>
                    </div>

                    {/* Live Hearing Banner when recording */}
                    {isRecording && (
                      <div
                        style={{
                          padding: "10px 14px",
                          background: "rgba(239, 68, 68, 0.08)",
                          border: "1px dashed rgba(239, 68, 68, 0.35)",
                          borderRadius: "8px",
                          fontSize: "0.85rem",
                          color: "#fca5a5",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: "10px",
                          marginBottom: "12px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1 }}>
                          <span style={{ fontWeight: "600", color: "#ef4444" }}>Hearing:</span>
                          <span style={{ fontStyle: "italic", color: "#f8fafc" }}>
                            &ldquo;{interimTranscript || voiceInput || "Listening for speech..."}&rdquo;
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => stopRecording(true)}
                          className="btn btn-recording"
                          style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                        >
                          <Square size={12} fill="#ffffff" />
                          Done Speaking
                        </button>
                      </div>
                    )}

                    {/* Microphone / Recording Error Banner */}
                    {recordingError && (
                      <div
                        style={{
                          padding: "10px 14px",
                          background: "rgba(239, 68, 68, 0.15)",
                          border: "1px solid rgba(239, 68, 68, 0.3)",
                          borderRadius: "8px",
                          color: "#fca5a5",
                          fontSize: "0.82rem",
                          marginBottom: "12px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: "8px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <AlertTriangle size={16} color="#f87171" />
                          <span>{recordingError}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => setRecordingError(null)}
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "#fca5a5",
                            cursor: "pointer",
                            fontSize: "0.8rem",
                          }}
                        >
                          ✕
                        </button>
                      </div>
                    )}

                    {/* Spoken Transcript Feed */}
                    <div
                      style={{
                        flex: 1,
                        overflowY: "auto",
                        display: "flex",
                        flexDirection: "column",
                        gap: "12px",
                        marginBottom: "16px",
                      }}
                    >
                      {voiceTranscript.map((item, idx) => (
                        <div
                          key={idx}
                          style={{
                            background:
                              item.speaker === "ai"
                                ? "rgba(99, 102, 241, 0.1)"
                                : "rgba(255, 255, 255, 0.03)",
                            border: "1px solid var(--border-color)",
                            padding: "12px 16px",
                            borderRadius: "10px",
                          }}
                        >
                          <span
                            style={{
                              display: "block",
                              fontSize: "0.72rem",
                              color: item.speaker === "ai" ? "#818cf8" : "#38bdf8",
                              fontWeight: "600",
                              marginBottom: "4px",
                              textTransform: "uppercase",
                            }}
                          >
                            {item.speaker === "ai" ? "🎙️ AI Agent (Spoken)" : "👤 Caller (Spoken Input)"}
                          </span>
                          <p style={{ fontSize: "0.9rem", color: "#f8fafc", lineHeight: "1.4" }}>
                            {item.text}
                          </p>
                        </div>
                      ))}
                      {voiceLoading && (
                        <div style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
                          Transcribing audio & orchestrating MCP tools...
                        </div>
                      )}
                      <div ref={chatScrollRef} />
                    </div>

                    {/* Spoken Response Input */}
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <input
                        type="text"
                        value={voiceInput}
                        onChange={(e) => setVoiceInput(e.target.value)}
                        placeholder={isRecording ? "Listening to your voice..." : "Speak into mic or type what you would say..."}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !voiceLoading) {
                            if (isRecording) {
                              stopRecording(true);
                            } else {
                              handleVoiceTurn();
                            }
                          }
                        }}
                        style={{
                          flex: 1,
                          padding: "12px 16px",
                          background: "var(--bg-input)",
                          border: isRecording ? "1px solid rgba(239, 68, 68, 0.5)" : "1px solid var(--border-color)",
                          borderRadius: "8px",
                          color: "#f8fafc",
                          fontSize: "0.9rem",
                          outline: "none",
                          transition: "border-color 0.2s ease",
                        }}
                      />

                      <button
                        type="button"
                        onClick={handleUseCurrentLocation}
                        disabled={locatingUser || voiceLoading || isRecording}
                        className="btn btn-secondary"
                        title="Share device GPS location on the voice call"
                        style={{
                          padding: "0 12px",
                          background: "rgba(56, 189, 248, 0.1)",
                          border: "1px solid rgba(56, 189, 248, 0.3)",
                          color: "#38bdf8",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                          fontSize: "0.82rem",
                          whiteSpace: "nowrap",
                          height: "44px",
                        }}
                      >
                        <Navigation size={14} style={{ animation: locatingUser ? "spin 1s linear infinite" : "none" }} />
                        {locatingUser ? "Locating..." : "📍 GPS"}
                      </button>

                      {/* Microphone Speak / Recording Button */}
                      {isRecording ? (
                        <button
                          type="button"
                          onClick={() => stopRecording(true)}
                          className="btn btn-recording"
                          title="Click to stop recording and send speech"
                          style={{
                            height: "44px",
                            padding: "0 16px",
                            fontSize: "0.85rem",
                            fontWeight: "600",
                            whiteSpace: "nowrap",
                          }}
                        >
                          <Square size={14} fill="#ffffff" />
                          Done Speaking
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={startRecording}
                          className="btn btn-primary"
                          disabled={voiceLoading}
                          title="Click to activate microphone and speak"
                          style={{
                            height: "44px",
                            padding: "0 16px",
                            fontSize: "0.85rem",
                            whiteSpace: "nowrap",
                            background: "#2563eb",
                          }}
                        >
                          <Mic size={16} />
                          Speak
                        </button>
                      )}

                      {/* Send Button for typed / edited input */}
                      <button
                        type="button"
                        onClick={() => {
                          if (isRecording) {
                            stopRecording(true);
                          } else {
                            handleVoiceTurn();
                          }
                        }}
                        className="btn btn-secondary"
                        disabled={voiceLoading || (!voiceInput.trim() && !isRecording)}
                        title="Send response"
                        style={{
                          height: "44px",
                          padding: "0 14px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <Send size={15} />
                      </button>

                      {/* Hang Up Button */}
                      <button
                        type="button"
                        onClick={endCall}
                        className="btn"
                        style={{
                          height: "44px",
                          background: "rgba(244, 63, 94, 0.15)",
                          color: "#fb7185",
                          border: "1px solid rgba(244, 63, 94, 0.3)",
                          padding: "0 14px",
                          whiteSpace: "nowrap",
                        }}
                      >
                        <PhoneOff size={16} />
                        Hang Up
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: MCP TOOL EXECUTION INSPECTOR */}
      {activeTab === "inspector" && (
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "24px" }}>
          {/* MCP Execution Log */}
          <div className="glass-card" style={{ padding: "20px" }}>
            <div style={{ marginBottom: "16px" }}>
              <h3 style={{ fontSize: "1.15rem", fontWeight: "600", color: "#f8fafc" }}>
                Model Context Protocol (MCP) Execution Log
              </h3>
              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                Audited record of all backend MCP tools invoked by the AI agent
              </p>
            </div>

            <div style={{ maxHeight: "650px", overflowY: "auto", display: "grid", gap: "12px" }}>
              {mcpLogs.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px", color: "var(--text-dim)" }}>
                  No MCP tools executed yet. Interact with the simulator to see live tool calls!
                </div>
              ) : (
                mcpLogs.map((log, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: "rgba(0,0,0,0.25)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "10px",
                      padding: "14px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "8px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span
                          style={{
                            background: "rgba(99, 102, 241, 0.2)",
                            color: "#818cf8",
                            padding: "3px 8px",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                            fontFamily: "monospace",
                            fontWeight: "600",
                          }}
                        >
                          {log.tool_name}
                        </span>
                        <span
                          style={{
                            background:
                              log.status === "success"
                                ? "rgba(16, 185, 129, 0.15)"
                                : "rgba(244, 63, 94, 0.15)",
                            color: log.status === "success" ? "#34d399" : "#fb7185",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            fontSize: "0.7rem",
                          }}
                        >
                          {log.status.toUpperCase()}
                        </span>
                      </div>

                      <span style={{ fontSize: "0.75rem", color: "#38bdf8", fontFamily: "monospace" }}>
                        ⚡ {log.latency_ms} ms
                      </span>
                    </div>

                    {/* Arguments & Result Accordion / Pre blocks */}
                    <div style={{ display: "grid", gap: "6px" }}>
                      <div>
                        <span style={{ fontSize: "0.7rem", color: "var(--text-dim)", textTransform: "uppercase" }}>
                          Arguments:
                        </span>
                        <pre
                          style={{
                            background: "rgba(0,0,0,0.4)",
                            padding: "8px",
                            borderRadius: "6px",
                            fontSize: "0.75rem",
                            color: "#e2e8f0",
                            overflowX: "auto",
                          }}
                        >
                          {JSON.stringify(log.arguments, null, 2)}
                        </pre>
                      </div>

                      <div>
                        <span style={{ fontSize: "0.7rem", color: "var(--text-dim)", textTransform: "uppercase" }}>
                          Result:
                        </span>
                        <pre
                          style={{
                            background: "rgba(0,0,0,0.4)",
                            padding: "8px",
                            borderRadius: "6px",
                            fontSize: "0.75rem",
                            color: "#34d399",
                            overflowX: "auto",
                          }}
                        >
                          {JSON.stringify(log.result || log.error, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* FCM Notifications Panel */}
          <div className="glass-card" style={{ padding: "20px" }}>
            <div style={{ marginBottom: "16px" }}>
              <h3 style={{ fontSize: "1.15rem", fontWeight: "600", color: "#f8fafc" }}>
                Dispatched Notifications ({notifications.length})
              </h3>
              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                Firebase Cloud Messaging (FCM) & push broadcasts
              </p>
            </div>

            <div style={{ maxHeight: "650px", overflowY: "auto", display: "grid", gap: "12px" }}>
              {notifications.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px", color: "var(--text-dim)" }}>
                  No notifications recorded yet. Book a ride to trigger passenger & driver alerts.
                </div>
              ) : (
                notifications.map((n, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "10px",
                      padding: "14px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "8px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <BellRing size={15} color="#fbbf24" />
                        <strong style={{ fontSize: "0.85rem", color: "#f8fafc" }}>
                          Ride #{n.ride_id} Confirmed
                        </strong>
                      </div>
                      <span
                        style={{
                          fontSize: "0.7rem",
                          background: "rgba(56, 189, 248, 0.15)",
                          color: "#38bdf8",
                          padding: "2px 6px",
                          borderRadius: "4px",
                        }}
                      >
                        {n.delivery_mode}
                      </span>
                    </div>

                    <div style={{ fontSize: "0.8rem", color: "#cbd5e1", marginBottom: "6px" }}>
                      <span style={{ color: "#38bdf8" }}>To Passenger ({n.employee_name}):</span>
                      <p style={{ marginTop: "2px", color: "var(--text-muted)" }}>{n.employee_message}</p>
                    </div>

                    <div style={{ fontSize: "0.8rem", color: "#cbd5e1" }}>
                      <span style={{ color: "#34d399" }}>To Driver ({n.driver_name}):</span>
                      <p style={{ marginTop: "2px", color: "var(--text-muted)" }}>{n.driver_message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
