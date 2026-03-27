# VGD Agente IA - Frontend

Frontend profesional en **Next.js 14** + **Tailwind CSS** + **ShadcN/ui** para el agente de IA.

## 📋 Características

- ✅ Dashboard con gráficos y tablas
- ✅ Chat conversacional con el agente Python
- ✅ Gestión de queries guardadas
- ✅ Autenticación con JWT
- ✅ Calendarios y Schedulers
- ✅ Tema oscuro/claro
- ✅ Responsive design

## 🚀 Instalación

```bash
cd frontend
npm install
```

## 💻 Desarrollo

```bash
npm run dev
```

Abre [http://localhost:3000](http://localhost:3000)

## 🔧 Build

```bash
npm run build
npm start
```

## 📁 Estructura

```
frontend/
├── app/
│   ├── components/      # Componentes reutilizables
│   ├── hooks/          # Custom hooks
│   ├── layout.tsx      # Layout global
│   ├── page.tsx        # Página principal
│   ├── dashboard/      # Dashboard
│   ├── chat/           # Chat agent
│   ├── queries/        # Queries guardadas
│   ├── auth/           # Autenticación
│   └── ...
├── lib/                # Utilidades y helpers
├── types/              # TypeScript types
├── services/           # API services
├── styles/             # CSS global
└── README.md
```

## 🔌 Integración con Backend

El Frontend se conecta con el backend Python en `http://localhost:8501` (Streamlit/FastAPI).

Ver [ARQUITECTURA_FE.md](./ARQUITECTURA_FE.md) para detalles completos.

## 📚 Tecnologías

- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **ShadcN/ui** - Componentes profesionales
- **Recharts** - Gráficos
- **React Hook Form** - Formularios
- **Zustand** - State management
- **Axios** - HTTP client
