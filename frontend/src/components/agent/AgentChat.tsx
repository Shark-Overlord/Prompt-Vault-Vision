import { FormEvent, useEffect, useState } from "react";
import { Bot, Loader2, Send } from "lucide-react";
import { useAgentChat, useAgentMessages } from "../../hooks/useAgent";
import type { AgentMessage } from "../../lib/types";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Textarea } from "../ui/textarea";
import { AgentActionConfirm } from "./AgentActionConfirm";
import { AgentSourceList } from "./AgentSourceList";

function MessageBubble({ message }: { message: AgentMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "ml-auto max-w-[82%]" : "mr-auto max-w-[88%]"}>
      <div className={isUser ? "rounded-lg bg-primary px-4 py-3 text-primary-foreground" : "rounded-lg border bg-muted/20 px-4 py-3"}>
        <div className="whitespace-pre-wrap text-sm leading-6">{message.content}</div>
      </div>
      {!isUser && <AgentSourceList sources={message.sources || []} />}
      {!isUser && <AgentActionConfirm actions={message.actions || []} />}
    </div>
  );
}

export function AgentChat() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const chat = useAgentChat();
  const { data: messages = [] } = useAgentMessages(threadId);

  useEffect(() => {
    if (chat.data?.thread_id) setThreadId(chat.data.thread_id);
  }, [chat.data?.thread_id]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message) return;
    chat.mutate({ message, thread_id: threadId });
    setDraft("");
  };

  const visibleMessages = messages.length ? messages : chat.data?.message ? [chat.data.message] : [];

  return (
    <Card className="min-h-[640px]">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          本地库智能体
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-[560px] flex-col gap-4 p-4">
        <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border bg-background/40 p-4">
          {!visibleMessages.length && (
            <div className="py-20 text-center text-sm text-muted-foreground">
              可以询问：我有哪些 Web UI Prompt？哪些候选配对最值得复查？以后优先低商用风险素材。
            </div>
          )}
          {visibleMessages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {chat.isPending && (
            <div className="mr-auto inline-flex items-center gap-2 rounded-lg border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              智能体正在检索本地库
            </div>
          )}
        </div>
        <form onSubmit={submit} className="flex gap-2">
          <Textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="搜索本地 Prompt 库、询问待复查项，或告诉智能体你的长期偏好..."
            className="min-h-16 resize-none"
          />
          <Button type="submit" disabled={chat.isPending || !draft.trim()} className="self-stretch">
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
