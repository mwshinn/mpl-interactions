from matplotlib.pyplot import subplots, close
from matplotlib import get_backend
from matplotlib.widgets import LassoSelector
from matplotlib.path import Path
from numpy import swapaxes, asarray, min, max
import numpy as np
from .utils import nearest_idx, ioff, figure

# functions that are methods
__all__ = [
    'heatmap_slicer',
    'zoom_factory',
    'panhandler',
    'image_segmenter'
]
def heatmap_slicer(X,Y,heatmaps, slices='horizontal',heatmap_names = None,max_cols=None,figsize=(18,9),linecolor='k',labels=('X','Y'),interaction_type='move'):
    
    """
    Compare horizontal and/or vertical slices accross multiple arrays.

    Parameters
    ----------
    X,Y : 1D array
    heatmaps : array_like
       must be 2-D or 3-D. If 3-D the last two axes should be (X,Y) 
    slice : {'horizontal', 'vertical', 'both'}
        Direction to draw slice on heatmap. both will draw horizontal and vertical traces on the same
        plot, while both_separate will make a line plot for each.
    heatmap_names : (String, String, ...)
        An iterable with the names of the heatmaps. If provided it must have as many names as there are heatmaps
    max_cols : int, optional - not working yet :(
        Maximum number of columns to allo   
    ax : matplolibt.Axes or None
        axes on which to 
    y_scale : string or tuple of floats, optional
        If a tuple it will be passed to ax.set_ylim. Other options are:
        'auto': rescale the y axis for every redraw
        'stretch': only ever expand the ylims.
    slider_format_string : string
        A valid format string, this will be used to render
        the current value of the parameter
    plot_kwargs : None, dict, or iterable of dicts
        Keyword arguments to pass to plot. If using multiple f's then plot_kwargs must be either
        None or be iterable.l
        figure size to pass to `plt.subplots`
    labels : (string, string), optional
    interaction_type : str
        Update on mouse movement or mouse click. Options are {'move','click'}

    Returns
    -------
    fig : matplotlib figure
    ax  : tuple of axes
    """
    horiz = vert = False
    if slices == 'both':
        num_line_axes = 2
        horiz_axis = -2
        vert_axis = -1
        horiz = vert = True
    else:
        horiz_axis = -1
        vert_axis = -1
        num_line_axes = 1
        if slices =='horizontal':
            horiz = True
        elif slices =='vertical':
            vert = True
        else:
            raise ValueError('Valid options for slices are {horizontal, vertical, both}')


    heatmaps = asarray(heatmaps)
    if heatmap_names is None:
        heatmap_names = [f'heatmap_{i}' for i in range(heatmaps.shape[0])]

    if heatmaps.ndim == 3:
        num_axes = num_line_axes + heatmaps.shape[0]
        if type(heatmap_names) is str or (len(heatmap_names) != heatmaps.shape[0]):
            raise ValueError('need to provide at least as many heatmap_names as heatmaps')
    elif heatmaps.ndim == 2:
        heatmaps = heatmaps.reshape(1,*heatmaps.shape)
        if type(heatmap_names) is str:
            heatmap_names = [heatmap_names]
        num_axes = num_line_axes + 1
    else:
        raise ValueError(f"heatmaps must be 2D or 3D but is {heatmaps.ndim}D")


    fig, axes = subplots(1,num_axes,figsize=figsize)
    hlines = []
    vlines = []
    init_idx = 0
    axes[0].set_ylabel(labels[1])
    for i,ax in enumerate(axes[:-num_line_axes]):
        ax.pcolormesh(X,Y,heatmaps[i])
        ax.set_xlabel(labels[0])
        ax.set_title(heatmap_names[i])
        if i>0:
            ax.set_yticklabels([])

        if horiz:
            data_line = axes[horiz_axis].plot(X,heatmaps[i,init_idx,:],label=f"{heatmap_names[i]}")[0]
            hlines.append((ax.axhline(Y[init_idx],color=linecolor),data_line))
        if vert:
            data_line = axes[vert_axis].plot(Y,heatmaps[i,:,init_idx],label=f"{heatmap_names[i]}")[0]
            vlines.append((ax.axvline(X[init_idx],color=linecolor),data_line))

    minimum = min(heatmaps)
    maximum = max(heatmaps)
    if vert:
        axes[vert_axis].set_title('Vertical')
        axes[vert_axis].set_ylim([minimum,maximum])
        axes[vert_axis].legend()
    if horiz:
        axes[horiz_axis].set_title('Horizontal')
        axes[horiz_axis].set_ylim([minimum,maximum])
        axes[horiz_axis].legend()

    def update_lines(event):
        if event.inaxes in axes[:-num_line_axes]:
            for i,lines in enumerate(hlines):
                y_idx = nearest_idx(Y,event.ydata)
                lines[0].set_ydata(Y[y_idx])
                lines[1].set_ydata(heatmaps[i,y_idx,:])
            for i,lines in enumerate(vlines):
                x_idx = nearest_idx(X,event.xdata)
                lines[0].set_xdata(X[x_idx])
                lines[1].set_ydata(heatmaps[i,:,x_idx])
        fig.canvas.draw_idle()
    if interaction_type == 'move':
        fig.canvas.mpl_connect('motion_notify_event',update_lines) 
    elif interaction_type == 'click':
        fig.canvas.mpl_connect('button_press_event',update_lines) 
    else:
        close(fig)
        raise ValueError(f'{interaction_type} is not a valid option for interaction_type, valid options are \'click\' or \'move\'')
    return fig,axes


# based on https://gist.github.com/tacaswell/3144287
def zoom_factory(ax, base_scale = 1.1):
    """
    Add ability to zoom with the scroll wheel.

    parameters
    ----------
    ax : matplotlib axes object
        axis on which to implement scroll to zoom
    base_scale : float
        how much zoom on each tick of scroll wheel
 
    returns
    -------
    disconnect_zoom : function
        call this to disconnect the scroll listener
    """
    def limits_to_range(lim):
        return lim[1] - lim[0]
    
    fig = ax.get_figure() # get the figure of interest
    fig.canvas.capture_scroll = True
    toolbar = fig.canvas.toolbar
    toolbar.push_current()
    orig_xlim = ax.get_xlim()
    orig_ylim = ax.get_ylim()
    orig_yrange = limits_to_range(orig_ylim)
    orig_xrange = limits_to_range(orig_xlim)
    orig_center = ((orig_xlim[0]+orig_xlim[1])/2, (orig_ylim[0]+orig_ylim[1])/2)
    def zoom_fun(event):
        # get the current x and y limits
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        # set the range
        cur_xrange = (cur_xlim[1] - cur_xlim[0])*.5
        cur_yrange = (cur_ylim[1] - cur_ylim[0])*.5
        xdata = event.xdata # get event x location
        ydata = event.ydata # get event y location
        if event.button == 'up':
            # deal with zoom in
            scale_factor = base_scale
        elif event.button == 'down':
            # deal with zoom out
            scale_factor = 1/base_scale
        else:
            # deal with something that should never happen
            scale_factor = 1
        # set new limits
        new_xlim = [xdata - (xdata-cur_xlim[0]) / scale_factor,
                    xdata + (cur_xlim[1]-xdata) / scale_factor]
        new_ylim = [ydata - (ydata-cur_ylim[0]) / scale_factor,
                        ydata + (cur_ylim[1]-ydata) / scale_factor]
        new_yrange = limits_to_range(new_ylim)
        new_xrange = limits_to_range(new_xlim)

        if abs(new_yrange)>abs(orig_yrange):
            new_ylim = orig_center[1] -new_yrange/2 , orig_center[1] +new_yrange/2
        if abs(new_xrange)>abs(orig_xrange):
            new_xlim = orig_center[0] -new_xrange/2 , orig_center[0] +new_xrange/2
        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)

        toolbar.push_current()
        ax.figure.canvas.draw_idle() # force re-draw


    # attach the call back
    cid = fig.canvas.mpl_connect('scroll_event',zoom_fun)
    def disconnect_zoom():
        fig.canvas.mpl_disconnect(cid)    

    #return the disconnect function
    return disconnect_zoom

class panhandler:
    """
    Enable panning a plot with any mouse button.
    
    button determines which button will be used (default right click)
    Left: 1
    Middle: 2
    Right: 3
    """
    def __init__(self, fig, button=3):
        self.fig = fig
        self._id_drag = None
        self.button = button
        self.fig.canvas.mpl_connect('button_press_event', self.press)
        self.fig.canvas.mpl_connect('button_release_event', self.release)

    def _cancel_action(self):
        self._xypress = []
        if self._id_drag:
            self.fig.canvas.mpl_disconnect(self._id_drag)
            self._id_drag = None
        
    def press(self, event):
        if event.button != self.button:
            self._cancel_action()
            return

        x, y = event.x, event.y

        self._xypress = []
        for i, a in enumerate(self.fig.get_axes()):
            if (x is not None and y is not None and a.in_axes(event) and
                    a.get_navigate() and a.can_pan()):
                a.start_pan(x, y, event.button)
                self._xypress.append((a, i))
                self._id_drag = self.fig.canvas.mpl_connect(
                    'motion_notify_event', self._mouse_move)

    def release(self, event):
        self._cancel_action()
        self.fig.canvas.mpl_disconnect(self._id_drag)

        for a, _ind in self._xypress:
            a.end_pan()
        if not self._xypress:
            self._cancel_action()
            return
        self._cancel_action()

    def _mouse_move(self, event):
        for a, _ind in self._xypress:
            # safer to use the recorded button at the _press than current
            # button: # multiple button can get pressed during motion...
            a.drag_pan(1, event.key, event.x, event.y)
        self.fig.canvas.draw_idle()

import matplotlib.cm as cm
from matplotlib.colors import to_rgba_array, TABLEAU_COLORS, XKCD_COLORS
class image_segmenter:
    """
    Manually segment an image with the lasso selector.
    """
    def __init__(self, img, nclasses = 1, mask = None, mask_colors = None, mask_alpha=.75, figsize=(10,10), cmap = 'viridis'):
        """
        parameters
        ----------
        img : array_like
            A valid argument to imshow
        nclasses : int, default 1
        mask: arraylike, optional
            If you want to pre-seed the mask
        mask_colors : None, color, or array of colors, optional
            the colors to use for each class. Unselected regions will always be totally transparent
        mask_alpha : float, default .75
            The alpha values to use for selected regions. This will always override the alpha values
            in mask_colors if any were passed
        figsize : (float, float), optional
            passed to plt.figure
        cmap : 'string'
            the colormap to use if img has shape (X,Y)
        """
        
        #ensure mask colors is iterable and the same length as the number of classes
        # choose colors from default color cycle?

        self.mask_alpha = mask_alpha

        if mask_colors is None:
            # this will break if there are more than 10 classes
            if nclasses <= 10:
                self.mask_colors = to_rgba_array(list(TABLEAU_COLORS)[:nclasses])
            else:
                # up to 949 classes. Hopefully that is always enough....
                self.mask_colors = to_rgba_array(list(XKCD_COLORS)[:nclasses])
        else:
            self.mask_colors = to_rgba_array(np.atleast_1d(mask_colors))
            # should probably check the shape here
        self.mask_colors[:,-1] = self.mask_alpha

        self._img = np.asarray(img)

        if mask is None:
            self.mask = np.zeros(self._img.shape[:2])
        else:
            self.mask = mask
        
        self._overlay = np.zeros((*self._img.shape[:2], 4))
        self.nclasses = nclasses
        for i in range(nclasses+1):
            idx = self.mask == i
            if i == 0:
                self._overlay[idx] = [0,0,0,0]
            else:
                self._overlay[idx] = self.mask_colors[i-1]
        with ioff:
            self.fig = figure(figsize=figsize)
            self.ax = self.fig.gca()
            self.displayed = self.ax.imshow(self._img)
            self._mask = self.ax.imshow(self._overlay)
    


        lineprops = {'color': 'black', 'linewidth': 1, 'alpha': 0.8}
        useblit = False if 'ipympl' in get_backend().lower() else True
        self.lasso = LassoSelector(self.ax, self._onselect, lineprops=lineprops, useblit=useblit)
        self.lasso.set_visible(True)
        
        pix_x = np.arange(self._img.shape[0])
        pix_y = np.arange(self._img.shape[1])
        xv, yv = np.meshgrid(pix_y,pix_x)
        self.pix = np.vstack( (xv.flatten(), yv.flatten()) ).T
        
        self.ph = panhandler(self.fig)
        self.disconnect_zoom = zoom_factory(self.ax)
        self.current_class = 1
        self.erasing = False
        
    def _onselect(self, verts):
        self.verts = verts
        p = Path(verts)
        self.indices = p.contains_points(self.pix, radius=0).reshape(self.mask.shape)
        if self.erasing:
            self.mask[self.indices] = 0
            self._overlay[self.indices] = [0,0,0,0]
        else:
            self.mask[self.indices] = self.current_class
            self._overlay[self.indices] = self.mask_colors[self.current_class-1]

        self._mask.set_data(self._overlay)
        self.fig.canvas.draw_idle()

    def _ipython_display_(self):
        display(self.fig.canvas)