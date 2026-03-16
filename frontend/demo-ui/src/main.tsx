import { Component, type ErrorInfo, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

function installDomSafetyPatch(): void {
  const marker = '__demo_ui_dom_patch_installed__'
  const globalRef = window as typeof window & { [key: string]: boolean | undefined }
  if (globalRef[marker]) {
    return
  }
  globalRef[marker] = true

  const nativeRemoveChild = Node.prototype.removeChild
  Node.prototype.removeChild = function removeChildPatched<T extends Node>(child: T): T {
    if (!child || child.parentNode !== this) {
      return child
    }
    return nativeRemoveChild.call(this, child) as T
  }
}

type RootErrorBoundaryState = {
  hasError: boolean
  message: string
}

class RootErrorBoundary extends Component<{ children: ReactNode }, RootErrorBoundaryState> {
  state: RootErrorBoundaryState = {
    hasError: false,
    message: '',
  }

  static getDerivedStateFromError(error: Error): RootErrorBoundaryState {
    return {
      hasError: true,
      message: error?.message || '页面渲染异常',
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('root_render_error', error, info)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="root-fallback">
          <h1>页面加载异常</h1>
          <p>前端发生运行时错误，已阻止白屏。请点击刷新后重试。</p>
          <p className="root-fallback-msg">错误信息：{this.state.message}</p>
          <button type="button" onClick={() => window.location.reload()}>
            刷新页面
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

installDomSafetyPatch()

createRoot(document.getElementById('root')!).render(
  <RootErrorBoundary>
    <App />
  </RootErrorBoundary>,
)
