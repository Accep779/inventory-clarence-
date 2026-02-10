"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface GlassCardProps extends React.ComponentProps<typeof Card> {
  children: React.ReactNode
  className?: string
  hoverEffect?: boolean
}

export function GlassCard({ children, className, hoverEffect = true, ...props }: GlassCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("h-full", className)}
    >
      <Card 
        className={cn(
          "bg-slate-900/40 backdrop-blur-xl border-slate-800/60 shadow-xl overflow-hidden active:scale-[0.99] transition-all duration-300",
          hoverEffect && "hover:bg-slate-900/60 hover:shadow-indigo-500/10 hover:border-indigo-500/30",
          className
        )} 
        {...props}
      >
        {children}
      </Card>
    </motion.div>
  )
}
