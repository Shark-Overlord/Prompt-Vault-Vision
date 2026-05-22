import { FormEvent, ReactNode, useEffect, useState } from "react";
import { Bot, Loader2, Send } from "lucide-react";
import { useAgentChat, useAgentMessages } from "../../hooks/useAgent";
import type { AgentMessage, AgentSource } from "../../lib/types";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Textarea } from "../ui/textarea";
import { AgentActionConfirm } from "./AgentActionConfirm";
import { AgentSourceDrawer, AgentSourceList } from "./AgentSourceList";

function sourceKey(source: AgentSource) {
  return `${source.type}/${source.id}`;
}

function InlineMarkdown({ text, onOpenAgentSource }: { text: string; onOpenAgentSource?: (key: string) => void }) {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text))) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    if (match[2]) {
      nodes.push(<strong key={match.index}>{match[2]}</strong>);
    } else if (match[3]) {
      nodes.push(
        <code key={match.index} className="rounded border bg-muted px-1 py-0.5 text-[0.85em]">
          {match[3]}
        </code>
      );
    } else if (match[4] && match[5]) {
      const href = match[5];
      if (href.startsWith("agent-source://")) {
        const key = href.replace("agent-source://", "");
        nodes.push(
          <button key={match.index} type="button" className="text-primary underline underline-offset-4" onClick={() => onOpenAgentSource?.(key)}>
            {match[4]}
          </button>
        );
      } else {
        nodes.push(
          <a key={match.index} href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer" className="text-primary underline underline-offset-4">
            {match[4]}
          </a>
        );
      }
    }
    lastIndex = pattern.lastIndex;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return <>{nodes}</>;
}

function MarkdownMessage({ content, isUser, onOpenAgentSource }: { content: string; isUser: boolean; onOpenAgentSource?: (key: string) => void }) {
  const lines = content.split(/\r?\n/);
  return (
    <div className={isUser ? "space-y-2 text-sm leading-6" : "space-y-3 text-sm leading-6"}>
      {lines.map((line, index) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={index} className="h-1" />;
        if (trimmed.startsWith("### ")) {
          return (
            <h4 key={index} className="pt-2 text-sm font-semibold text-foreground">
              <InlineMarkdown text={trimmed.slice(4)} onOpenAgentSource={onOpenAgentSource} />
            </h4>
          );
        }
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={index} className="pt-2 text-base font-semibold text-foreground">
              <InlineMarkdown text={trimmed.slice(3)} onOpenAgentSource={onOpenAgentSource} />
            </h3>
          );
        }
        if (trimmed.startsWith("- ")) {
          return (
            <div key={index} className="flex gap-2">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-60" />
              <span>
                <InlineMarkdown text={trimmed.slice(2)} onOpenAgentSource={onOpenAgentSource} />
              </span>
            </div>
          );
        }
        if (trimmed.startsWith("> ")) {
          return (
            <blockquote key={index} className="border-l-2 pl-3 text-muted-foreground">
              <InlineMarkdown text={trimmed.slice(2)} onOpenAgentSource={onOpenAgentSource} />
            </blockquote>
          );
        }
        return (
          <p key={index}>
            <InlineMarkdown text={trimmed} onOpenAgentSource={onOpenAgentSource} />
          </p>
        );
      })}
    </div>
  );
}

function MessageBubble({ message }: { message: AgentMessage }) {
  const isUser = message.role === "user";
  const [selectedSource, setSelectedSource] = useState<AgentSource | null>(null);
  const sources = message.sources || [];
  const openSourceByKey = (key: string) => {
    const source = sources.find((item) => sourceKey(item) === key);
    if (source) setSelectedSource(source);
  };
  return (
    <div className={isUser ? "ml-auto max-w-[82%]" : "mr-auto max-w-[88%]"}>
      <div className={isUser ? "rounded-lg bg-primary px-4 py-3 text-primary-foreground" : "rounded-lg border bg-muted/20 px-4 py-3"}>
        <MarkdownMessage content={message.content} isUser={isUser} onOpenAgentSource={openSourceByKey} />
      </div>
      {!isUser && <AgentSourceList sources={sources} onOpenSource={setSelectedSource} />}
      {!isUser && <AgentActionConfirm actions={message.actions || []} />}
      {!isUser && <AgentSourceDrawer source={selectedSource} open={Boolean(selectedSource)} onOpenChange={(open) => !open && setSelectedSource(null)} />}
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
        <div className="text-xs text-muted-foreground">Agent Chat</div>
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
