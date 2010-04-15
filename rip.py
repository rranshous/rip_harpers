from urllib2 import urlopen
from urlparse import urljoin
from BeautifulSoup import BeautifulSoup as BS
import re
import pickle
from datetime import date
import htmlentitydefs
from Queue import Queue, Empty, Full
from threading import Thread

def thread_out_work(args,f,thread_percentage=.25,fake_it=False):
    results = []
    if fake_it:
        for arg in args:
            results.append(f(*arg))
    else:
        work_queue = Queue()
        result_queue = Queue()
        threads = []
        map(work_queue.put_nowait,args)
        for i in xrange(len(args)*thread_percentage):
            threads.append(thread_out_function(f,work_queue,result_queue))
            threads[-1].start()
        for thread in threads:
            thread.join()
        results = [x for x in result_queue.get_nowait()]
    return results

def thread_out_function(f,in_queue,out_queue):
    def threaded(f,in_queue,out_queue):
        while not in_queue.empty() or out_queue.empty():
            try:
                args = in_queue.get(True,2)
                r = f(*args)
                out_queue.put(r,True)
            except Empty, ex:
                print 'empty'
        return True

    return Thread(target=threaded,kwargs={'f': f,
                                          'in_queue':in_queue,
                                          'out_queue':out_queue})

def strip_extra_spaces(string):
    return re.sub(r'\s+',' ',string)

# ty: http://effbot.org/zone/re-sub.htm#unescape-html
def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)

def clean(s):
    return strip_extra_spaces(unescape(s))

def get_contents(elements):
    s = ''
    for element in elements:
        if element.string:
            s += clean(element.string)
        else:
            for content in element.contents:
                if content.string:
                    s += clean(content.string)
                else:
                    s += get_contents(content)
    return s.strip()

def get_all_data():
    # each arg gets *'d
    args = map(lambda a: (a,),range(1985,date.today().year+1))
    year_data = thread_out_work(args,get_year_data,1,True)
    return year_data


def get_year_data(year):
    args = []
    for month in xrange(1,13):
        if year == date.today().year and month > date.today().month:
            break # can't see into the future
        args.append((year,month))

    month_data = thread_out_work(args,get_month_data,1,True)

    return month_data

def get_month_data(year,month):
    print 'grabbing %s:%s' % (year,month)
    lines = urlopen('http://harpers.org/index/%s/%s' % (year,month))
    html = ''.join(lines)
    soup = BS(html)

    line_sets = []
    lines = soup.findAll('div',{'class':'index-line'})
    source_lines = soup.findAll('div',{'class':re.compile(r'^source.*')})
    print len(lines)
    print len(source_lines)
    for line,source in zip(lines,source_lines):
        # we are going to get the month, the content for the line, and the stat
        # some of the entries dont have months, if that is the case than they are
        # tied to the line before them
        data = {}
        is_associated = False
        months = line.findAll('span',{'class':'month'})

        # there are lines that match the selector but aren't what we want
        if not months: continue

        # of there is no month link
        if not [1 for x in months if x.a is not None]:
            # associated to previous
            data['month'] = line_sets[-1][-1]['month']
            data['year'] = line_sets[-1][-1]['year']
            is_associated = True
        else:
            data['month'], data['year'] = get_contents(months).split('/')

        bodies = line.findAll('span',{'class':'line'})
        data['body'] = get_contents(bodies)

        stats = line.findAll('span',{'class':'stat'})
        data['stat'] = get_contents(stats)

        # source line includes share links
        data['source'] = get_contents([source.contents[0]])

        # see where we want to add
        if is_associated and line_sets:
            line_sets[-1].append(data)
        else:
            line_sets.append([data])

    print line_sets
    print
    return line_sets

if __name__ == "__main__":
    data = get_all_data()
    with file('/tmp/all_data.pickle','w') as fh:
        pickle.dump(data,fh)
