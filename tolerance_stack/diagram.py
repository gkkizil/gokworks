"""Toolkit-independent 1D chain, sensitivity and simulation drawings."""

from .models import fmt


def setup(canvas,appearance):
    dark=appearance=='Dark'
    colors=dict(bg='#1C2431' if dark else '#FFFFFF',text='#E8EEF7' if dark else '#20344F',
                muted='#A5B3C8' if dark else '#5D718D',accent='#80B6F5' if dark else '#2466B2',
                border='#344155' if dark else '#D7E0EC',danger='#F0A5B1' if dark else '#B23D53')
    canvas.delete('all');canvas.configure(background=colors['bg'])
    return colors,canvas.winfo_width(),canvas.winfo_height()


def text(canvas,c,x,y,value,**kwargs):
    canvas.create_text(x,y,text=value,fill=c['text'],font=('Segoe UI',-14),**kwargs)


def draw_chain(canvas,project,appearance):
    c,w,h=setup(canvas,appearance)
    if not project.terms:
        text(canvas,c,w/2,h/2-10,'Soldan bir ölçü seçip + Topla veya − Çıkar ile başlayın.',width=w-45)
        text(canvas,c,w/2,h/2+20,'Örnek: 50 − 20 − 29,8 = 0,2 mm');return
    dimensions={d.id:d for d in project.dimensions};shown=project.terms[:10]
    step=(w-70)/max(1,len(shown));y=h*.45
    for i,t in enumerate(shown):
        d=dimensions.get(t.dimension_id);a,b=35+i*step,35+(i+1)*step
        x0,x1=(a+7,b-7) if t.direction>0 else (b-7,a+7)
        canvas.create_line(x0,y,x1,y,fill=c['accent'],width=2,arrow='last',arrowshape=(7,9,4))
        canvas.create_line(a,y-9,a,y+9,fill=c['muted'])
        text(canvas,c,(a+b)/2,y-25,f'L{i+1}  {"+" if t.direction>0 else "−"}'+(f' ×{t.factor}' if t.factor!=1 else ''))
        text(canvas,c,(a+b)/2,y+30,fmt(d.nominal,3) if d else 'Silinmiş',width=step-6)
    text(canvas,c,25,18,'Ölçü zinciri · + ekler / − çıkarır',anchor='w')
    text(canvas,c,25,h-16,'Şematik · CAD geometrisi doğrulanmaz.'+
         (f' İlk 10 / {len(project.terms)} ölçü; tümü tabloda.' if len(project.terms)>10 else ''),anchor='w',width=w-50)


def draw_contributions(canvas,result,appearance):
    c,w,h=setup(canvas,appearance)
    if result is None: text(canvas,c,w/2,h/2,'Hesaptan sonra kritik ölçü katkıları gösterilir.');return
    statistical=result.sigma is not None
    values=sorted(result.contributions,key=lambda x:x.variance_percent if statistical else x.worst_case_percent,reverse=True)[:10]
    text(canvas,c,18,18,'VARYANS KATKISI (%)' if statistical else 'WORST-CASE BANT KATKISI (%)',anchor='w')
    row=(h-65)/max(1,len(values))
    for i,value in enumerate(values):
        percent=value.variance_percent if statistical else value.worst_case_percent
        y=40+i*row
        text(canvas,c,15,y+7,value.name[:28],anchor='w',width=w*.30,justify='left')
        x=w*.36;right=w-65
        canvas.create_rectangle(x,y,right,y+14,fill=c['border'],outline='')
        canvas.create_rectangle(x,y,x+(right-x)*percent/100,y+14,fill=c['accent'],outline='')
        text(canvas,c,w-12,y+7,f'%{fmt(percent,1)}',anchor='e')


def draw_histogram(canvas,project,result,appearance):
    c,w,h=setup(canvas,appearance)
    if result is None or result.monte_carlo is None:
        text(canvas,c,w/2,h/2,'Histogram için Monte Carlo yöntemini seçin.');return
    histogram=result.monte_carlo['histogram'];counts=histogram['counts'];peak=max(counts) or 1
    low,high=histogram['minimum'],histogram['maximum'];left,right=55,w-30;top,bottom=40,h-55
    for i,count in enumerate(counts):
        x0=left+i*(right-left)/len(counts);x1=left+(i+1)*(right-left)/len(counts)
        canvas.create_rectangle(x0,bottom-count/peak*(bottom-top),x1,bottom,fill=c['accent'],outline=c['bg'])
    for limit in (project.acceptance_min,project.acceptance_max):
        if limit is not None and low<=float(limit)<=high and low!=high:
            x=left+(float(limit)-low)/(high-low)*(right-left)
            canvas.create_line(x,top,x,bottom,fill=c['danger'],width=2,dash=(5,3))
    text(canvas,c,left,18,'MONTE CARLO · örnek dağılımı',anchor='w')
    text(canvas,c,left,bottom+18,fmt(low),anchor='w');text(canvas,c,right,bottom+18,fmt(high)+' mm',anchor='e')
    text(canvas,c,left,h-13,'Kırmızı çizgi: kabul sınırı · Örnek uçları Worst-Case sınırları değildir.',anchor='w')
