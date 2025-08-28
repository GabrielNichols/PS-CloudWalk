# InfinitePay Assistant Frontend

Uma interface de chat moderna e responsiva para o assistente de IA da InfinitePay, construída com React, TypeScript e Tailwind CSS.

## 🚀 Funcionalidades

- **Interface de ChatGPT-like**: Design moderno e intuitivo
- **Streaming em Tempo Real**: Respostas são exibidas palavra por palavra
- **Fontes e Metadados**: Exibição estruturada de fontes e informações de desempenho
- **Sessões Persistentes**: Baseado em fingerprint do navegador (sem necessidade de login)
- **Responsivo**: Funciona perfeitamente em desktop e mobile
- **TypeScript**: Totalmente tipado para melhor desenvolvimento

## 🛠️ Tecnologias Utilizadas

- **React 19** - Framework UI
- **TypeScript** - Tipagem estática
- **Tailwind CSS** - Estilização utilitária
- **Axios** - Cliente HTTP
- **Lucide React** - Ícones
- **React Markdown** - Renderização de Markdown

## 📦 Instalação

```bash
# Instalar dependências
npm install

# Iniciar servidor de desenvolvimento
npm start

# Construir para produção
npm run build
```

## ⚙️ Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
REACT_APP_API_URL=https://your-api-domain.com
```

Se não definida, a API será acessada localmente em `http://localhost:8000`.

## 🔧 Scripts Disponíveis

```bash
npm start          # Inicia o servidor de desenvolvimento
npm run build      # Constrói o projeto para produção
npm test           # Executa os testes
npm run eject      # Remove a configuração do Create React App
```

## 🚀 Deploy no Vercel

### Deploy Automático

1. **Conecte seu repositório ao Vercel**
2. **Configure as variáveis de ambiente no Vercel**:
   - `REACT_APP_API_URL`: URL da sua API FastAPI

### Deploy Manual

```bash
# Construir o projeto
npm run build

# O resultado estará na pasta `build/`
# Faça upload desta pasta para seu provedor de hospedagem
```

## 🏗️ Arquitetura

### Estrutura de Pastas

```
frontend/
├── src/
│   ├── components/        # Componentes React
│   │   └── ChatInterface.tsx
│   ├── hooks/            # Hooks customizados
│   │   └── useChat.ts
│   ├── services/         # Serviços e APIs
│   │   └── api.ts
│   ├── types/            # Definições TypeScript
│   │   └── types.ts
│   ├── utils/            # Utilitários
│   │   └── session.ts
│   ├── App.tsx           # Componente principal
│   └── index.tsx         # Ponto de entrada
├── public/               # Arquivos estáticos
└── package.json
```

### Componentes Principais

- **ChatInterface**: Interface principal do chat
- **useChat**: Hook para gerenciamento de estado do chat
- **api.ts**: Serviço para comunicação com a API backend
- **session.ts**: Utilitários de gerenciamento de sessão

## 🔐 Gerenciamento de Sessões

O frontend utiliza um sistema de fingerprinting baseado em:
- User Agent
- Idioma do navegador
- Resolução de tela
- Timezone
- Suporte a Web Storage

Isso permite sessões persistentes sem necessidade de autenticação.

## 📡 Comunicação com Backend

### API Endpoints

- `POST /api/v1/message` - Envio de mensagem (fallback)
- `POST /api/v1/message/stream` - Streaming de mensagens (SSE)

### Formato de Resposta

```typescript
interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  sources?: Array<{
    url: string;
    title?: string;
  }>;
  metadata?: {
    agent?: string;
    confidence?: number;
    latency_ms?: number;
    mode?: string;
  };
}
```

## 🎨 Personalização

### Cores e Tema

O tema é configurado no `tailwind.config.js`. As cores principais são:

```javascript
colors: {
  'chatgpt-gray': '#202123',
  'chatgpt-dark': '#343541',
  'chatgpt-light': '#444654',
}
```

### Estilos Customizados

Estilos adicionais podem ser adicionados em `src/index.css`.

## 🧪 Testes

```bash
npm test
```

## 🔧 Troubleshooting

### Erro: `message.timestamp.toLocaleTimeString is not a function`

**Sintomas:** Tela fica cinza e aparece erro no console sobre `toLocaleTimeString`

**Causa:** Dados corrompidos no localStorage com timestamps inválidos

**Soluções:**

1. **Limpeza Automática (Recomendado):**
   ```javascript
   // Abra o console do navegador (F12) e execute:
   emergencyClearAllData()
   // Depois recarregue a página
   ```

2. **Limpeza Manual:**
   - Abra o console do navegador (F12)
   - Vá para Application/Storage > Local Storage
   - Delete as chaves `chat_session_id` e `chat_messages`
   - Recarregue a página

3. **Prevenção:**
   - A aplicação agora valida automaticamente todos os timestamps
   - Dados corrompidos são corrigidos automaticamente
   - Novos dados são salvos com formato consistente

### Erro: `Loading PostCSS "tailwindcss" plugin failed`

**Causa:** Conflito com dependências do Tailwind

**Solução:**
```bash
rm -rf node_modules package-lock.json
npm install
```

### Erro 404 ao enviar mensagens

**Causa:** Backend não está rodando ou URL incorreta

**Soluções:**
- Verifique se o backend está rodando em `http://localhost:8000`
- Verifique as variáveis de ambiente `REACT_APP_API_URL`
- Para produção, configure a URL completa da API

### Interface sem formatação

**Causa:** CSS não carregado ou conflitante

**Solução:**
- Recarregue a página (Ctrl+F5)
- Limpe o cache do navegador
- Verifique se não há conflitos de CSS de outras extensões

## 📝 Desenvolvimento

### Convenções de Código

- Use TypeScript para todas as novas funcionalidades
- Mantenha os componentes pequenos e reutilizáveis
- Use hooks customizados para lógica complexa
- Siga as convenções do React e TypeScript

### Adicionando Novos Componentes

1. Crie o componente em `src/components/`
2. Defina os tipos em `src/types/`
3. Exporte o componente no arquivo principal
4. Adicione estilos Tailwind conforme necessário

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 🆘 Suporte

Para dúvidas ou problemas:

1. Verifique os [Issues](https://github.com/your-repo/issues) existentes
2. Abra um novo issue com descrição detalhada
3. Inclua screenshots e passos para reproduzir o problema

---

**InfinitePay Assistant** - Transformando o atendimento ao cliente com IA 🤖✨